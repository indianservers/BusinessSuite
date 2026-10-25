import * as tf from '@tensorflow/tfjs';

export type LlamaConfig = { hidden_size:number; num_hidden_layers:number; num_attention_heads:number;
  num_key_value_heads:number; intermediate_size:number; vocab_size:number; rms_norm_eps:number;
  rope_theta:number; max_position_embeddings:number; tie_word_embeddings:boolean };

/** Llama causal decoder using TF.js ops exclusively. HF [out,in] weights,
 * grouped-query attention, split-half RoPE and request-local KV caches. */
export class TfjsLlama {
  private cache: {k:tf.Tensor3D;v:tf.Tensor3D}[] = [];
  private position = 0;
  constructor(readonly config:LlamaConfig, private weights:tf.NamedTensorMap) {
    const c=config;
    if(c.hidden_size % c.num_attention_heads || c.num_attention_heads % c.num_key_value_heads ||
       (c.hidden_size/c.num_attention_heads)%2) throw new Error('Unsupported attention dimensions');
    const expected:Record<string,number[]>={'model.embed_tokens.weight':[c.vocab_size,c.hidden_size], 'model.norm.weight':[c.hidden_size]};
    for(let i=0;i<c.num_hidden_layers;i++) {
      const p=`model.layers.${i}.`;
      for(const n of ['input_layernorm','post_attention_layernorm']) expected[p+n+'.weight']=[c.hidden_size];
      for(const n of ['q_proj','o_proj']) expected[p+'self_attn.'+n+'.weight']=[c.hidden_size,c.hidden_size];
      for(const n of ['k_proj','v_proj']) expected[p+'self_attn.'+n+'.weight']=[c.num_key_value_heads*c.hidden_size/c.num_attention_heads,c.hidden_size];
      for(const n of ['gate_proj','up_proj']) expected[p+'mlp.'+n+'.weight']=[c.intermediate_size,c.hidden_size];
      expected[p+'mlp.down_proj.weight']=[c.hidden_size,c.intermediate_size];
    }
    if(!c.tie_word_embeddings)expected['lm_head.weight']=[c.vocab_size,c.hidden_size];
    for(const [name,shape] of Object.entries(expected))if(weights[name]?.shape.join(',')!==shape.join(','))throw new Error(`Invalid tensor ${name}`);
  }
  reset() { for(const c of this.cache){c?.k.dispose();c?.v.dispose();} this.cache=[];this.position=0; }
  dispose() { this.reset();tf.dispose(this.weights); }
  private norm(x:tf.Tensor2D,name:string) {
    return x.mul(x.square().mean(-1,true).add(this.config.rms_norm_eps).rsqrt()).mul(this.weights[name]) as tf.Tensor2D;
  }
  private linear(x:tf.Tensor2D,name:string) { return tf.matMul(x,this.weights[name] as tf.Tensor2D,false,true); }
  private rotary(x:tf.Tensor3D,offset:number) {
    const [heads,length,dim]=x.shape;
    const frequencies=tf.tensor1d(Array.from({length:dim/2},(_,i)=>1/this.config.rope_theta**(2*i/dim)));
    const angles=tf.range(offset,offset+length).expandDims(1).mul(frequencies.expandDims(0));
    const cos=angles.cos().expandDims(0),sin=angles.sin().expandDims(0);
    const a=x.slice([0,0,0],[heads,length,dim/2]),b=x.slice([0,0,dim/2],[heads,length,dim/2]);
    return tf.concat([a.mul(cos).sub(b.mul(sin)),b.mul(cos).add(a.mul(sin))],-1) as tf.Tensor3D;
  }
  /** Caller owns returned next-token logits. */
  forward(ids:number[]):tf.Tensor1D {
    if(!ids.length || this.position+ids.length>this.config.max_position_embeddings)throw new Error('Context limit');
    const c=this.config,n=ids.length,d=c.hidden_size/c.num_attention_heads,offset=this.position;
    const logits=tf.tidy(()=>{
      let x=tf.gather(this.weights['model.embed_tokens.weight'],tf.tensor1d(ids,'int32')) as tf.Tensor2D;
      for(let i=0;i<c.num_hidden_layers;i++) {
        const previousX=x;
        x=tf.tidy(()=>{
          const p=`model.layers.${i}.`,h=this.norm(x,p+'input_layernorm.weight');
          const q=this.rotary(this.linear(h,p+'self_attn.q_proj.weight').reshape([n,c.num_attention_heads,d]).transpose([1,0,2]) as tf.Tensor3D,offset);
          let k=this.rotary(this.linear(h,p+'self_attn.k_proj.weight').reshape([n,c.num_key_value_heads,d]).transpose([1,0,2]) as tf.Tensor3D,offset);
          let v=this.linear(h,p+'self_attn.v_proj.weight').reshape([n,c.num_key_value_heads,d]).transpose([1,0,2]) as tf.Tensor3D;
          const previous=this.cache[i];
          if(previous){k=tf.concat([previous.k,k],1);v=tf.concat([previous.v,v],1);}
          this.cache[i]={k:tf.keep(k),v:tf.keep(v)};
          previous?.k.dispose();previous?.v.dispose();
          const repeat=c.num_attention_heads/c.num_key_value_heads,total=offset+n;
          const expand=(t:tf.Tensor3D)=>t.expandDims(1).tile([1,repeat,1,1]).reshape([c.num_attention_heads,total,d]) as tf.Tensor3D;
          const mask=tf.tensor2d(Array.from({length:n*total},(_,j)=>j%total>offset+Math.floor(j/total)?-1e9:0),[n,total]);
          const scores=tf.matMul(q,expand(k),false,true).div(Math.sqrt(d)).add(mask);
          const attention=tf.matMul(tf.softmax(scores,-1),expand(v)).transpose([1,0,2]).reshape([n,c.hidden_size]) as tf.Tensor2D;
          const residual=x.add(this.linear(attention,p+'self_attn.o_proj.weight')) as tf.Tensor2D;
          const norm=this.norm(residual,p+'post_attention_layernorm.weight');
          const gate=this.linear(norm,p+'mlp.gate_proj.weight');
          const feed=gate.mul(tf.sigmoid(gate)).mul(this.linear(norm,p+'mlp.up_proj.weight')) as tf.Tensor2D;
          return residual.add(this.linear(feed,p+'mlp.down_proj.weight')) as tf.Tensor2D;
        });
        previousX.dispose();
      }
      const last=this.norm(x,'model.norm.weight').slice([n-1,0],[1,c.hidden_size]);
      return this.linear(last,c.tie_word_embeddings?'model.embed_tokens.weight':'lm_head.weight').reshape([c.vocab_size]) as tf.Tensor1D;
    });
    this.position+=n;
    return logits;
  }
}
