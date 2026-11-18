(function(){"use strict";function Im(n,t){return t.forEach(function(e){e&&typeof e!="string"&&!Array.isArray(e)&&Object.keys(e).forEach(function(s){if(s!=="default"&&!(s in n)){var r=Object.getOwnPropertyDescriptor(e,s);Object.defineProperty(n,s,r.get?r:{enumerable:!0,get:function(){return e[s]}})}})}),Object.freeze(n)}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Sm=1e-7,vm=1e-4;class Nm{constructor(t,e){this.backend=t,this.dataMover=e,this.data=new WeakMap,this.dataIdsCount=0}get(t){return this.data.has(t)||this.dataMover.moveData(this.backend,t),this.data.get(t)}set(t,e){this.dataIdsCount++,this.data.set(t,e)}has(t){return this.data.has(t)}delete(t){return this.dataIdsCount--,this.data.delete(t)}numDataIds(){return this.dataIdsCount}}class wc{refCount(t){return ge("refCount")}incRef(t){return ge("incRef")}timerAvailable(){return!0}time(t){return ge("time")}read(t){return ge("read")}readSync(t){return ge("readSync")}readToGPU(t,e){return ge("readToGPU")}numDataIds(){return ge("numDataIds")}disposeData(t,e){return ge("disposeData")}write(t,e,s){return ge("write")}move(t,e,s,r,o){return ge("move")}createTensorFromGPUData(t,e,s){return ge("createTensorFromGPUData")}memory(){return ge("memory")}floatPrecision(){return ge("floatPrecision")}epsilon(){return this.floatPrecision()===32?Sm:vm}dispose(){return ge("dispose")}}function ge(n){throw new Error(`'${n}' not yet implemented or not found in the registry. This kernel may not be supported by the tfjs backend you have chosen`)}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function $m(n){let t=n.length,e=0;for(;t>0;)e=Math.random()*t|0,t--,ds(n,t,e)}function bi(n,t,e){return Math.max(n,Math.min(t,e))}function ds(n,t,e){const s=n[t];n[t]=n[e],n[e]=s}function v(n,t){if(!n)throw new Error(typeof t=="string"?t:t())}function kc(n,t,e=""){v(oe(n,t),()=>e+` Shapes ${n} and ${t} must match`)}function xc(n){v(n!=null,()=>"The input to the tensor constructor must be a non-null value.")}function Z(n){if(n.length===0)return 1;let t=n[0];for(let e=1;e<n.length;e++)t*=n[e];return t}function oe(n,t){if(n===t)return!0;if(n==null||t==null||n.length!==t.length)return!1;for(let e=0;e<n.length;e++)if(n[e]!==t[e])return!1;return!0}function $r(n){return n%1===0}function Tr(n,t){return t<=n.length?n:n+" ".repeat(t-n.length)}function Tm(n,t){let e=1,s=-1;for(let o=0;o<n.length;++o)if(n[o]>=0)e*=n[o];else if(n[o]===-1){if(s!==-1)throw Error(`Shapes can only have 1 implicit size. Found -1 at dim ${s} and dim ${o}`);s=o}else if(n[o]<0)throw Error(`Shapes can not be < 0. Found ${n[o]} at dim ${o}`);if(s===-1){if(t>0&&t!==e)throw Error(`Size(${t}) must match the product of shape ${n}`);return n}if(e===0)throw Error(`Cannot infer the missing size in [${n}] when there are 0 elements`);if(t%e!==0)throw Error(`The implicit shape can't be a fractional number. Got ${t} / ${e}`);const r=n.slice();return r[s]=t/e,r}function Ft(n,t){const e=t.length;return n=n==null?t.map((s,r)=>r):[].concat(n),v(n.every(s=>s>=-e&&s<e),()=>`All values in axis param must be in range [-${e}, ${e}) but got axis ${n}`),v(n.every(s=>$r(s)),()=>`All values in axis param must be integers but got axis ${n}`),n.map(s=>s<0?e+s:s)}function Cm(n,t){const e=[],s=[],r=t!=null&&Array.isArray(t)&&t.length===0,o=t==null||r?null:Ft(t,n).sort();let i=0;for(let a=0;a<n.length;++a){if(o!=null){if(o[i]===a&&n[a]!==1)throw new Error(`Can't squeeze axis ${a} since its dim '${n[a]}' is not 1`);(o[i]==null||o[i]>a)&&n[a]===1&&(e.push(n[a]),s.push(a)),o[i]<=a&&i++}n[a]!==1&&(e.push(n[a]),s.push(a))}return{newShape:e,keptDims:s}}function he(n,t){return Gt(n,t)}function Gt(n,t){let e=null;if(n==null||n==="float32")e=new Float32Array(t);else if(n==="int32")e=new Int32Array(t);else if(n==="bool")e=new Uint8Array(t);else if(n==="string")e=new Array(t);else throw new Error(`Unknown data type ${n}`);return e}function Am(n,t){for(let e=0;e<n.length;e++){const s=n[e];if(isNaN(s)||!isFinite(s))throw Error(`A tensor of type ${t} being uploaded contains ${s}.`)}}function Em(n){return n==="bool"||n==="complex64"||n==="float32"||n==="int32"||n==="string"}function Dm(n,t){return!(t==="complex64"||t==="float32"&&n!=="complex64"||t==="int32"&&n!=="float32"&&n!=="complex64"||t==="bool"&&n==="bool")}function yi(n){if(n==="float32"||n==="int32")return 4;if(n==="complex64")return 8;if(n==="bool")return 1;throw new Error(`Unknown dtype ${n}`)}function Fm(n){if(n==null)return 0;let t=0;return n.forEach(e=>t+=e.length),t}function Cr(n){return typeof n=="string"||n instanceof String}function Mm(n){return typeof n=="boolean"}function wi(n){return typeof n=="number"}function Ws(n){return Array.isArray(n)?Ws(n[0]):n instanceof Float32Array?"float32":n instanceof Int32Array||n instanceof Uint8Array||n instanceof Uint8ClampedArray?"int32":wi(n)?"float32":Cr(n)?"string":Mm(n)?"bool":"float32"}function ki(n){return!!(n&&n.constructor&&n.call&&n.apply)}function it(n){const t=n.length;if(t<2)return[];const e=new Array(t-1);e[t-2]=n[t-1];for(let s=t-3;s>=0;--s)e[s]=e[s+1]*n[s+1];return e}function Ic(n,t,e,s=!1){const r=new Array;if(t.length===1){const o=t[0]*(s?2:1);for(let i=0;i<o;i++)r[i]=e[n+i]}else{const o=t[0],i=t.slice(1),a=i.reduce((l,c)=>l*c)*(s?2:1);for(let l=0;l<o;l++)r[l]=Ic(n+l*a,i,e,s)}return r}function Le(n,t,e=!1){if(n.length===0)return t[0];const s=n.reduce((r,o)=>r*o)*(e?2:1);if(s===0)return[];if(s!==t.length)throw new Error(`[${n}] does not match the input size ${t.length}${e?" for a complex tensor":""}.`);return Ic(0,n,t,e)}function Rm(n,t){if(Array.isArray(n))return n;if(t==="float32")return n instanceof Float32Array?n:new Float32Array(n);if(t==="int32")return n instanceof Int32Array?n:new Int32Array(n);if(t==="bool"||t==="string")return Uint8Array.from(new Int32Array(n));throw new Error(`Unknown dtype ${t}`)}function xi(n,t){const e=ie(n,t);for(let s=0;s<e.length;s++)e[s]=1;return e}function ie(n,t){if(t==null||t==="float32"||t==="complex64")return new Float32Array(n);if(t==="int32")return new Int32Array(n);if(t==="bool")return new Uint8Array(n);throw new Error(`Unknown data type ${t}`)}function Sc(n,t){const e=n.reduce((s,r)=>s*r,1);if(t==null||t==="float32")return Le(n,new Float32Array(e));if(t==="int32")return Le(n,new Int32Array(e));if(t==="bool")return Le(n,new Uint8Array(e));throw new Error(`Unknown data type ${t}`)}function dn(n){n.forEach(t=>{v(Number.isInteger(t)&&t>=0,()=>`Tensor must have a shape comprised of positive integers but got shape [${n}].`)})}function je(n,t,e){if(t===0)return 0;if(t===1)return n[0];let s=n[n.length-1];for(let r=0;r<n.length-1;++r)s+=e[r]*n[r];return s}function fs(n,t,e){if(t===0)return[];if(t===1)return[n];const s=new Array(t);for(let r=0;r<s.length-1;++r)s[r]=Math.floor(n/e[r]),n-=s[r]*e[r];return s[s.length-1]=n,s}function Ii(n){return n&&n.then&&typeof n.then=="function"}/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const vc="tfjsflags";class zm{constructor(t){this.global=t,this.flags={},this.flagRegistry={},this.urlFlags={},this.getQueryParams=Lm,this.populateURLFlags()}setPlatform(t,e){this.platform!=null&&(gt().getBool("IS_TEST")||gt().getBool("PROD")||console.warn(`Platform ${this.platformName} has already been set. Overwriting the platform with ${t}.`)),this.platformName=t,this.platform=e}registerFlag(t,e,s){if(this.flagRegistry[t]={evaluationFn:e,setHook:s},this.urlFlags[t]!=null){const r=this.urlFlags[t];gt().getBool("IS_TEST")||gt().getBool("PROD")||console.warn(`Setting feature override from URL ${t}: ${r}.`),this.set(t,r)}}async getAsync(t){return t in this.flags?this.flags[t]:(this.flags[t]=await this.evaluateFlag(t),this.flags[t])}get(t){if(t in this.flags)return this.flags[t];const e=this.evaluateFlag(t);if(Ii(e))throw new Error(`Flag ${t} cannot be synchronously evaluated. Please use getAsync() instead.`);return this.flags[t]=e,this.flags[t]}getNumber(t){return this.get(t)}getBool(t){return this.get(t)}getString(t){return this.get(t)}getFlags(){return this.flags}get features(){return this.flags}set(t,e){if(this.flagRegistry[t]==null)throw new Error(`Cannot set flag ${t} as it has not been registered.`);this.flags[t]=e,this.flagRegistry[t].setHook!=null&&this.flagRegistry[t].setHook(e)}evaluateFlag(t){if(this.flagRegistry[t]==null)throw new Error(`Cannot evaluate flag '${t}': no evaluation function found.`);return this.flagRegistry[t].evaluationFn()}setFlags(t){this.flags=Object.assign({},t)}reset(){this.flags={},this.urlFlags={},this.populateURLFlags()}populateURLFlags(){if(typeof this.global>"u"||typeof this.global.location>"u"||typeof this.global.location.search>"u")return;const t=this.getQueryParams(this.global.location.search);vc in t&&t[vc].split(",").forEach(s=>{const[r,o]=s.split(":");this.urlFlags[r]=_m(r,o)})}}function Lm(n){const t={};return n.replace(/[?&]([^=?&]+)(?:=([^&]*))?/g,(e,...s)=>(Om(t,s[0],s[1]),s.join("="))),t}function Om(n,t,e){n[decodeURIComponent(t)]=decodeURIComponent(e||"")}function _m(n,t){const e=t.toLowerCase();return e==="true"||e==="false"?e==="true":`${+e}`===e?+e:t}function gt(){return Nc}let Nc=null;function Bm(n){Nc=n}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */let Si;function $c(){if(Si==null){let n;if(typeof window<"u")n=window;else if(typeof global<"u")n=global;else if(typeof process<"u")n=process;else if(typeof self<"u")n=self;else throw new Error("Could not find a global object");Si=n}return Si}function Pm(){const n=$c();return n._tfGlobals==null&&(n._tfGlobals=new Map),n._tfGlobals}function vi(n,t){const e=Pm();if(e.has(n))return e.get(n);{const s=t();return e.set(n,s),e.get(n)}}const Ni="Abs",$i="Acos",Ti="Acosh",Vs="Add",Tc="AddN",Cc="All",Ac="Any",Ci="ArgMax",Ec="ArgMin",Ai="Asin",Ei="Asinh",Di="Atan",Fi="Atanh",Mi="Atan2",Ri="AvgPool",Dc="AvgPoolGrad",zi="AvgPool3D",Fc="AvgPool3DGrad",Li="BatchMatMul",Oi="BatchToSpaceND",Mc="Bincount",Rc="BitwiseAnd",Wm="BroadcastTo",Vm="BroadcastArgs",Ar="Cast",_i="Ceil",Er="ClipByValue",zc="Complex",Bi="ComplexAbs",Pi="Concat",Wi="Conv2D",Lc="Conv2DBackpropFilter",Vi="Conv2DBackpropInput",Gi="Conv3D",Oc="Conv3DBackpropFilterV2",_c="Conv3DBackpropInputV2",Dr="Cos",Fr="Cosh",Bc="Cumprod",Ui="Cumsum",Pc="CropAndResize",Wc="DenseBincount",Gm="DepthToSpace",Hi="DepthwiseConv2dNative",Vc="DepthwiseConv2dNativeBackpropFilter",Gc="DepthwiseConv2dNativeBackpropInput",Um="Diag",Uc="Dilation2D",qi="Dilation2DBackpropInput",ji="Dilation2DBackpropFilter",Hm="Draw",Mr="RealDiv",Hc="Einsum",Rr="Elu",qc="EluGrad",zr="Erf",Ki="Equal",Lr="Exp",Xi="ExpandDims",Zi="Expm1",qm="FFT",jc="Fill",Kc="FlipLeftRight",Or="Floor",_r="FloorDiv",Ji="FusedBatchNorm",Yi="GatherV2",jm="GatherNd",Qi="Greater",Br="GreaterEqual",Pr="Identity",Km="IFFT",Xc="Imag",ta="IsFinite",ea="IsInf",na="IsNan",sa="LeakyRelu",ra="Less",oa="LessEqual",Xm="LinSpace",Wr="Log",Vr="Log1p",ia="LogicalAnd",aa="LogicalNot",Zc="LogicalOr",Zm="LogSoftmax",Jc="LRN",Yc="LRNGrad",la="Max",Gr="Maximum",ca="MaxPool",Qc="MaxPoolGrad",ua="MaxPool3D",tu="MaxPool3DGrad",Jm="MaxPoolWithArgmax",ha="Mean",da="Min",Ur="Minimum",eu="MirrorPad",fa="Mod",Ym="Multinomial",Hr="Multiply",pa="Neg",ma="NotEqual",nu="NonMaxSuppressionV3",su="NonMaxSuppressionV4",ru="NonMaxSuppressionV5",ga="OnesLike",ba="OneHot",ya="Pack",wa="PadV2",qr="Pow",ka="Prelu",ou="Prod",Qm="RaggedGather",tg="RaggedRange",eg="RaggedTensorToTensor",iu="Range",au="Real",xa="Reciprocal",jr="Relu",Ia="Reshape",Sa="ResizeNearestNeighbor",lu="ResizeNearestNeighborGrad",va="ResizeBilinear",cu="ResizeBilinearGrad",Kr="Relu6",Na="Reverse",Xr="Round",Zr="Rsqrt",ng="ScatterNd",sg="TensorScatterUpdate",rg="SearchSorted",$a="Select",Jr="Selu",Ta="Slice",Yr="Sin",Qr="Sinh",Ca="Sign",to="Sigmoid",eo="Softplus",no="Sqrt",Aa="Sum",Ea="SpaceToBatchND",Da="SplitV",Fa="Softmax",og="SparseFillEmptyRows",ig="SparseReshape",ag="SparseSegmentMean",lg="SparseSegmentSum",cg="SparseToDense",Ma="SquaredDifference",uu="Square",hu="StaticRegexReplace",ug="StridedSlice",hg="StringNGrams",dg="StringSplit",fg="StringToHashBucketFast",so="Sub",Ra="Tan",ro="Tanh",oo="Tile",pg="TopK",du="Transform",Gs="Transpose",mg="Unique",za="Unpack",La="UnsortedSegmentSum",Oa="ZerosLike",io="Step",fu="RotateWithOffset",_a="_FusedMatMul",Ba="FusedConv2D",gg="FusedDepthwiseConv2D";/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function In(...n){gt().getBool("IS_TEST")||gt().getBool("PROD")||console.warn(...n)}/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const ao=vi("kernelRegistry",()=>new Map),Pa=vi("gradRegistry",()=>new Map);function pu(n,t){const e=bu(n,t);return ao.get(e)}function mu(n){return Pa.get(n)}function gu(n){const t=ao.entries(),e=[];for(;;){const{done:s,value:r}=t.next();if(s)break;const[o,i]=r,[a]=o.split("_");a===n&&e.push(i)}return e}function bg(n){const{kernelName:t,backendName:e}=n,s=bu(t,e);ao.has(s)&&In(`The kernel '${t}' for backend '${e}' is already registered`),ao.set(s,n)}function yg(n){const{kernelName:t}=n;Pa.has(t)&&gt().getBool("DEBUG")&&In(`Overriding the gradient for '${t}'`),Pa.set(t,n)}function bu(n,t){return`${t}_${n}`}/**
 * @license
 * Copyright 2023 Google LLC.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function yu(n){return n instanceof Float32Array||n instanceof Int32Array||n instanceof Uint8Array||n instanceof Uint8ClampedArray}function wg(n){return n&&n.__esModule&&Object.prototype.hasOwnProperty.call(n,"default")?n.default:n}function kg(n){if(Object.prototype.hasOwnProperty.call(n,"__esModule"))return n;var t=n.default;if(typeof t=="function"){var e=function s(){return this instanceof s?Reflect.construct(t,arguments,this.constructor):t.apply(this,arguments)};e.prototype=t.prototype}else e={};return Object.defineProperty(e,"__esModule",{value:!0}),Object.keys(n).forEach(function(s){var r=Object.getOwnPropertyDescriptor(n,s);Object.defineProperty(e,s,r.get?r:{enumerable:!0,get:function(){return n[s]}})}),e}var Wa,wu;function xg(){if(wu)return Wa;wu=1,Wa=t;var n=null;try{n=new WebAssembly.Instance(new WebAssembly.Module(new Uint8Array([0,97,115,109,1,0,0,0,1,13,2,96,0,1,127,96,4,127,127,127,127,1,127,3,7,6,0,1,1,1,1,1,6,6,1,127,1,65,0,11,7,50,6,3,109,117,108,0,1,5,100,105,118,95,115,0,2,5,100,105,118,95,117,0,3,5,114,101,109,95,115,0,4,5,114,101,109,95,117,0,5,8,103,101,116,95,104,105,103,104,0,0,10,191,1,6,4,0,35,0,11,36,1,1,126,32,0,173,32,1,173,66,32,134,132,32,2,173,32,3,173,66,32,134,132,126,34,4,66,32,135,167,36,0,32,4,167,11,36,1,1,126,32,0,173,32,1,173,66,32,134,132,32,2,173,32,3,173,66,32,134,132,127,34,4,66,32,135,167,36,0,32,4,167,11,36,1,1,126,32,0,173,32,1,173,66,32,134,132,32,2,173,32,3,173,66,32,134,132,128,34,4,66,32,135,167,36,0,32,4,167,11,36,1,1,126,32,0,173,32,1,173,66,32,134,132,32,2,173,32,3,173,66,32,134,132,129,34,4,66,32,135,167,36,0,32,4,167,11,36,1,1,126,32,0,173,32,1,173,66,32,134,132,32,2,173,32,3,173,66,32,134,132,130,34,4,66,32,135,167,36,0,32,4,167,11])),{}).exports}catch{}function t($,x,F){this.low=$|0,this.high=x|0,this.unsigned=!!F}t.prototype.__isLong__,Object.defineProperty(t.prototype,"__isLong__",{value:!0});function e($){return($&&$.__isLong__)===!0}t.isLong=e;var s={},r={};function o($,x){var F,M,O;return x?($>>>=0,(O=0<=$&&$<256)&&(M=r[$],M)?M:(F=a($,($|0)<0?-1:0,!0),O&&(r[$]=F),F)):($|=0,(O=-128<=$&&$<128)&&(M=s[$],M)?M:(F=a($,$<0?-1:0,!1),O&&(s[$]=F),F))}t.fromInt=o;function i($,x){if(isNaN($))return x?y:b;if(x){if($<0)return y;if($>=p)return T}else{if($<=-g)return C;if($+1>=g)return S}return $<0?i(-$,x).neg():a($%f|0,$/f|0,x)}t.fromNumber=i;function a($,x,F){return new t($,x,F)}t.fromBits=a;var l=Math.pow;function c($,x,F){if($.length===0)throw Error("empty string");if($==="NaN"||$==="Infinity"||$==="+Infinity"||$==="-Infinity")return b;if(typeof x=="number"?(F=x,x=!1):x=!!x,F=F||10,F<2||36<F)throw RangeError("radix");var M;if((M=$.indexOf("-"))>0)throw Error("interior hyphen");if(M===0)return c($.substring(1),x,F).neg();for(var O=i(l(F,8)),L=b,B=0;B<$.length;B+=8){var G=Math.min(8,$.length-B),W=parseInt($.substring(B,B+G),F);if(G<8){var V=i(l(F,G));L=L.mul(V).add(i(W))}else L=L.mul(O),L=L.add(i(W))}return L.unsigned=x,L}t.fromString=c;function u($,x){return typeof $=="number"?i($,x):typeof $=="string"?c($,x):a($.low,$.high,typeof x=="boolean"?x:$.unsigned)}t.fromValue=u;var h=65536,d=1<<24,f=h*h,p=f*f,g=p/2,m=o(d),b=o(0);t.ZERO=b;var y=o(0,!0);t.UZERO=y;var k=o(1);t.ONE=k;var w=o(1,!0);t.UONE=w;var I=o(-1);t.NEG_ONE=I;var S=a(-1,2147483647,!1);t.MAX_VALUE=S;var T=a(-1,-1,!0);t.MAX_UNSIGNED_VALUE=T;var C=a(0,-2147483648,!1);t.MIN_VALUE=C;var N=t.prototype;return N.toInt=function(){return this.unsigned?this.low>>>0:this.low},N.toNumber=function(){return this.unsigned?(this.high>>>0)*f+(this.low>>>0):this.high*f+(this.low>>>0)},N.toString=function(x){if(x=x||10,x<2||36<x)throw RangeError("radix");if(this.isZero())return"0";if(this.isNegative())if(this.eq(C)){var F=i(x),M=this.div(F),O=M.mul(F).sub(this);return M.toString(x)+O.toInt().toString(x)}else return"-"+this.neg().toString(x);for(var L=i(l(x,6),this.unsigned),B=this,G="";;){var W=B.div(L),V=B.sub(W.mul(L)).toInt()>>>0,U=V.toString(x);if(B=W,B.isZero())return U+G;for(;U.length<6;)U="0"+U;G=""+U+G}},N.getHighBits=function(){return this.high},N.getHighBitsUnsigned=function(){return this.high>>>0},N.getLowBits=function(){return this.low},N.getLowBitsUnsigned=function(){return this.low>>>0},N.getNumBitsAbs=function(){if(this.isNegative())return this.eq(C)?64:this.neg().getNumBitsAbs();for(var x=this.high!=0?this.high:this.low,F=31;F>0&&(x&1<<F)==0;F--);return this.high!=0?F+33:F+1},N.isZero=function(){return this.high===0&&this.low===0},N.eqz=N.isZero,N.isNegative=function(){return!this.unsigned&&this.high<0},N.isPositive=function(){return this.unsigned||this.high>=0},N.isOdd=function(){return(this.low&1)===1},N.isEven=function(){return(this.low&1)===0},N.equals=function(x){return e(x)||(x=u(x)),this.unsigned!==x.unsigned&&this.high>>>31===1&&x.high>>>31===1?!1:this.high===x.high&&this.low===x.low},N.eq=N.equals,N.notEquals=function(x){return!this.eq(x)},N.neq=N.notEquals,N.ne=N.notEquals,N.lessThan=function(x){return this.comp(x)<0},N.lt=N.lessThan,N.lessThanOrEqual=function(x){return this.comp(x)<=0},N.lte=N.lessThanOrEqual,N.le=N.lessThanOrEqual,N.greaterThan=function(x){return this.comp(x)>0},N.gt=N.greaterThan,N.greaterThanOrEqual=function(x){return this.comp(x)>=0},N.gte=N.greaterThanOrEqual,N.ge=N.greaterThanOrEqual,N.compare=function(x){if(e(x)||(x=u(x)),this.eq(x))return 0;var F=this.isNegative(),M=x.isNegative();return F&&!M?-1:!F&&M?1:this.unsigned?x.high>>>0>this.high>>>0||x.high===this.high&&x.low>>>0>this.low>>>0?-1:1:this.sub(x).isNegative()?-1:1},N.comp=N.compare,N.negate=function(){return!this.unsigned&&this.eq(C)?C:this.not().add(k)},N.neg=N.negate,N.add=function(x){e(x)||(x=u(x));var F=this.high>>>16,M=this.high&65535,O=this.low>>>16,L=this.low&65535,B=x.high>>>16,G=x.high&65535,W=x.low>>>16,V=x.low&65535,U=0,q=0,K=0,j=0;return j+=L+V,K+=j>>>16,j&=65535,K+=O+W,q+=K>>>16,K&=65535,q+=M+G,U+=q>>>16,q&=65535,U+=F+B,U&=65535,a(K<<16|j,U<<16|q,this.unsigned)},N.subtract=function(x){return e(x)||(x=u(x)),this.add(x.neg())},N.sub=N.subtract,N.multiply=function(x){if(this.isZero())return b;if(e(x)||(x=u(x)),n){var F=n.mul(this.low,this.high,x.low,x.high);return a(F,n.get_high(),this.unsigned)}if(x.isZero())return b;if(this.eq(C))return x.isOdd()?C:b;if(x.eq(C))return this.isOdd()?C:b;if(this.isNegative())return x.isNegative()?this.neg().mul(x.neg()):this.neg().mul(x).neg();if(x.isNegative())return this.mul(x.neg()).neg();if(this.lt(m)&&x.lt(m))return i(this.toNumber()*x.toNumber(),this.unsigned);var M=this.high>>>16,O=this.high&65535,L=this.low>>>16,B=this.low&65535,G=x.high>>>16,W=x.high&65535,V=x.low>>>16,U=x.low&65535,q=0,K=0,j=0,Y=0;return Y+=B*U,j+=Y>>>16,Y&=65535,j+=L*U,K+=j>>>16,j&=65535,j+=B*V,K+=j>>>16,j&=65535,K+=O*U,q+=K>>>16,K&=65535,K+=L*V,q+=K>>>16,K&=65535,K+=B*W,q+=K>>>16,K&=65535,q+=M*U+O*V+L*W+B*G,q&=65535,a(j<<16|Y,q<<16|K,this.unsigned)},N.mul=N.multiply,N.divide=function(x){if(e(x)||(x=u(x)),x.isZero())throw Error("division by zero");if(n){if(!this.unsigned&&this.high===-2147483648&&x.low===-1&&x.high===-1)return this;var F=(this.unsigned?n.div_u:n.div_s)(this.low,this.high,x.low,x.high);return a(F,n.get_high(),this.unsigned)}if(this.isZero())return this.unsigned?y:b;var M,O,L;if(this.unsigned){if(x.unsigned||(x=x.toUnsigned()),x.gt(this))return y;if(x.gt(this.shru(1)))return w;L=y}else{if(this.eq(C)){if(x.eq(k)||x.eq(I))return C;if(x.eq(C))return k;var B=this.shr(1);return M=B.div(x).shl(1),M.eq(b)?x.isNegative()?k:I:(O=this.sub(x.mul(M)),L=M.add(O.div(x)),L)}else if(x.eq(C))return this.unsigned?y:b;if(this.isNegative())return x.isNegative()?this.neg().div(x.neg()):this.neg().div(x).neg();if(x.isNegative())return this.div(x.neg()).neg();L=b}for(O=this;O.gte(x);){M=Math.max(1,Math.floor(O.toNumber()/x.toNumber()));for(var G=Math.ceil(Math.log(M)/Math.LN2),W=G<=48?1:l(2,G-48),V=i(M),U=V.mul(x);U.isNegative()||U.gt(O);)M-=W,V=i(M,this.unsigned),U=V.mul(x);V.isZero()&&(V=k),L=L.add(V),O=O.sub(U)}return L},N.div=N.divide,N.modulo=function(x){if(e(x)||(x=u(x)),n){var F=(this.unsigned?n.rem_u:n.rem_s)(this.low,this.high,x.low,x.high);return a(F,n.get_high(),this.unsigned)}return this.sub(this.div(x).mul(x))},N.mod=N.modulo,N.rem=N.modulo,N.not=function(){return a(~this.low,~this.high,this.unsigned)},N.and=function(x){return e(x)||(x=u(x)),a(this.low&x.low,this.high&x.high,this.unsigned)},N.or=function(x){return e(x)||(x=u(x)),a(this.low|x.low,this.high|x.high,this.unsigned)},N.xor=function(x){return e(x)||(x=u(x)),a(this.low^x.low,this.high^x.high,this.unsigned)},N.shiftLeft=function(x){return e(x)&&(x=x.toInt()),(x&=63)===0?this:x<32?a(this.low<<x,this.high<<x|this.low>>>32-x,this.unsigned):a(0,this.low<<x-32,this.unsigned)},N.shl=N.shiftLeft,N.shiftRight=function(x){return e(x)&&(x=x.toInt()),(x&=63)===0?this:x<32?a(this.low>>>x|this.high<<32-x,this.high>>x,this.unsigned):a(this.high>>x-32,this.high>=0?0:-1,this.unsigned)},N.shr=N.shiftRight,N.shiftRightUnsigned=function(x){if(e(x)&&(x=x.toInt()),x&=63,x===0)return this;var F=this.high;if(x<32){var M=this.low;return a(M>>>x|F<<32-x,F>>>x,this.unsigned)}else return x===32?a(F,0,this.unsigned):a(F>>>x-32,0,this.unsigned)},N.shru=N.shiftRightUnsigned,N.shr_u=N.shiftRightUnsigned,N.toSigned=function(){return this.unsigned?a(this.low,this.high,!1):this},N.toUnsigned=function(){return this.unsigned?this:a(this.low,this.high,!0)},N.toBytes=function(x){return x?this.toBytesLE():this.toBytesBE()},N.toBytesLE=function(){var x=this.high,F=this.low;return[F&255,F>>>8&255,F>>>16&255,F>>>24,x&255,x>>>8&255,x>>>16&255,x>>>24]},N.toBytesBE=function(){var x=this.high,F=this.low;return[x>>>24,x>>>16&255,x>>>8&255,x&255,F>>>24,F>>>16&255,F>>>8&255,F&255]},t.fromBytes=function(x,F,M){return M?t.fromBytesLE(x,F):t.fromBytesBE(x,F)},t.fromBytesLE=function(x,F){return new t(x[0]|x[1]<<8|x[2]<<16|x[3]<<24,x[4]|x[5]<<8|x[6]<<16|x[7]<<24,F)},t.fromBytesBE=function(x,F){return new t(x[4]<<24|x[5]<<16|x[6]<<8|x[7],x[0]<<24|x[1]<<16|x[2]<<8|x[3],F)},Wa}var ku=xg(),xu=wg(ku),Ig=Im({__proto__:null,default:xu},[ku]);/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const qn=xu||Ig;function lo(n){return qn.fromString(n,!0,16)}const Iu=lo("c3a5c85c97cb3127"),jn=lo("b492b66fbe98f273"),ce=lo("9ae16a3b2f90404f");function Va(n){return n.xor(n.shru(47))}function Su(n,t,e){const s=n.slice(t,t+e);return qn.fromBytes(Array.from(s),!0,!0)}function $t(n,t){return Su(n,t,8)}function vu(n,t){return Su(n,t,4)}function Zt(n,t){return t===0?n:n.shru(t).or(n.shl(64-t))}function Sn(n,t,e=lo("9ddfea08eb382d69")){let s=n.xor(t).mul(e);s=s.xor(s.shru(47));let r=t.xor(s).mul(e);return r=r.xor(r.shru(47)),r=r.mul(e),r}function Sg(n,t,e,s,r,o){r=r.add(n),o=Zt(o.add(r).add(s),21);const i=r;return r=r.add(t),r=r.add(e),o=o.add(Zt(r,44)),[r.add(s),o.add(i)]}function co(n,t,e,s){return Sg($t(n,t),$t(n,t+8),$t(n,t+16),$t(n,t+24),e,s)}function vg(n,t=n.length){if(t>=8){const e=ce.add(t*2),s=$t(n,0).add(ce),r=$t(n,t-8),o=Zt(r,37).mul(e).add(s),i=Zt(s,25).add(r).mul(e);return Sn(o,i,e)}if(t>=4){const e=ce.add(t*2),s=vu(n,0);return Sn(s.shl(3).add(t),vu(n,t-4),e)}if(t>0){const e=n[0],s=n[t>>1],r=n[t-1],o=e+(s<<8),i=t+(r<<2);return Va(ce.mul(o).xor(Iu.mul(i))).mul(ce)}return ce}function Ng(n,t=n.length){const e=ce.add(t*2),s=$t(n,0).mul(jn),r=$t(n,8),o=$t(n,t-8).mul(e),i=$t(n,t-16).mul(ce);return Sn(Zt(s.add(r),43).add(Zt(o,30)).add(i),s.add(Zt(r.add(ce),18)).add(o),e)}function $g(n,t=n.length){const e=ce.add(t*2),s=$t(n,0).mul(ce),r=$t(n,8),o=$t(n,t-8).mul(e),i=$t(n,t-16).mul(ce),a=Zt(s.add(r),43).add(Zt(o,30)).add(i),l=Sn(a,s.add(Zt(r.add(ce),18)).add(o),e),c=$t(n,16).mul(e),u=$t(n,24),h=a.add($t(n,t-32)).mul(e),d=l.add($t(n,t-24)).mul(e);return Sn(Zt(c.add(u),43).add(Zt(h,30)).add(d),c.add(Zt(u.add(s),18)).add(h),e)}function Tg(n,t=n.length){const e=qn.fromNumber(81,!0);if(t<=32)return t<=16?vg(n,t):Ng(n,t);if(t<=64)return $g(n,t);let s=e,r=e.mul(jn).add(113),o=Va(r.mul(ce).add(113)).mul(ce),i=[qn.UZERO,qn.UZERO],a=[qn.UZERO,qn.UZERO];s=s.mul(ce).add($t(n,0));let l=0;const c=(t-1>>6)*64,u=c+(t-1&63)-63;do s=Zt(s.add(r).add(i[0]).add($t(n,l+8)),37).mul(jn),r=Zt(r.add(i[1]).add($t(n,l+48)),42).mul(jn),s=s.xor(a[1]),r=r.add(i[0]).add($t(n,l+40)),o=Zt(o.add(a[0]),33).mul(jn),i=co(n,l,i[1].mul(jn),s.add(a[0])),a=co(n,l+32,o.add(a[1]),r.add($t(n,l+16))),[o,s]=[s,o],l+=64;while(l!==c);const h=jn.add(o.and(255).shl(1));return l=u,a[0]=a[0].add(t-1&63),i[0]=i[0].add(a[0]),a[0]=a[0].add(i[0]),s=Zt(s.add(r).add(i[0]).add($t(n,l+8)),37).mul(h),r=Zt(r.add(i[1]).add($t(n,l+48)),42).mul(h),s=s.xor(a[1].mul(9)),r=r.add(i[0].mul(9).add($t(n,l+40))),o=Zt(o.add(a[0]),33).mul(h),i=co(n,l,i[1].mul(h),s.add(a[0])),a=co(n,l+32,o.add(a[1]),r.add($t(n,l+16))),[o,s]=[s,o],Sn(Sn(i[0],a[0],h).add(Va(r).mul(Iu)).add(o),Sn(i[1],a[1],h).add(s),h)}/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ga(n,t){return t==="string"?Xn(n):Kn([n],t)}function Cg(n,t){return n instanceof Float32Array&&t==="float32"||n instanceof Int32Array&&t==="int32"||n instanceof Uint8Array&&t==="bool"}function Kn(n,t){if(t==="string")throw new Error("Cannot convert a string[] to a TypedArray");if(Array.isArray(n)&&(n=Hs(n)),gt().getBool("DEBUG")&&Am(n,t),Cg(n,t))return n;if(t==null||t==="float32"||t==="complex64")return new Float32Array(n);if(t==="int32")return new Int32Array(n);if(t==="bool"){const e=new Uint8Array(n.length);for(let s=0;s<e.length;++s)Math.round(n[s])!==0&&(e[s]=1);return e}else throw new Error(`Unknown data type ${t}`)}function vn(){return gt().platform.now()}function Xn(n,t="utf-8"){return t=t||"utf-8",gt().platform.encode(n,t)}function Us(n,t="utf-8"){return t=t||"utf-8",gt().platform.decode(n,t)}function Ne(n){return gt().platform.isTypedArray!=null?gt().platform.isTypedArray(n):yu(n)}function Hs(n,t=[],e=!1){if(t==null&&(t=[]),typeof n=="boolean"||typeof n=="number"||typeof n=="string"||Ii(n)||n==null||Ne(n)&&e)t.push(n);else if(Array.isArray(n)||Ne(n))for(let s=0;s<n.length;++s)Hs(n[s],t,e);else{let s=-1;for(const r of Object.keys(n))/^([1-9]+[0-9]*|0)$/.test(r)&&(s=Math.max(s,Number(r)));for(let r=0;r<=s;r++)Hs(n[r],t,e)}return t}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class Ag{constructor(t,e){this.backendTimer=t,this.logger=e,e==null&&(this.logger=new Dg)}profileKernel(t,e,s){let r;const o=()=>{r=s()};let i;const a=vn();if(this.backendTimer.timerAvailable())i=this.backendTimer.time(o);else{o();for(const c of r)c.dataSync();i=Promise.resolve({kernelMs:vn()-a})}if(gt().getBool("CHECK_COMPUTATION_FOR_ERRORS"))for(let c=0;c<r.length;c++){const u=r[c];u.data().then(h=>{Eg(h,u.dtype,t)})}return{kernelName:t,outputs:r,inputs:e,timeMs:i.then(c=>c.kernelMs),extraInfo:i.then(c=>c.getExtraProfileInfo!=null?c.getExtraProfileInfo():"")}}logKernelProfile(t){const{kernelName:e,outputs:s,timeMs:r,inputs:o,extraInfo:i}=t;s.forEach(a=>{Promise.all([a.data(),r,i]).then(l=>{this.logger.logKernelProfile(e,a,l[0],l[1],o,l[2])})})}}function Eg(n,t,e){if(t!=="float32")return!1;for(let s=0;s<n.length;s++){const r=n[s];if(isNaN(r)||!isFinite(r))return console.warn(`Found ${r} in the result of '${e}'`),!0}return!1}class Dg{logKernelProfile(t,e,s,r,o,i){const a=typeof r=="number"?Tr(`${r}ms`,9):r.error,l=Tr(t,25),c=e.rank,u=e.size,h=Tr(e.shape.toString(),14);let d="";for(const f in o){const p=o[f];if(p!=null){const g=p.shape||e.shape,m=g.length;d+=`${f}: ${m}D ${m>0?g:""} `}}console.log(`%c${l}	%c${a}	%c${c}D ${h}	%c${u}	%c${d}	%c${i}`,"font-weight:bold","color:red","color:blue","color: orange","color: green","color: steelblue")}}/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Fg(n,t,e){const s={},r={};for(let l=0;l<t.length;l++)s[t[l].id]=!0;for(let l=0;l<n.length;l++){const c=n[l],u=c.inputs;for(const h in u){const d=u[h];let f=!1;for(let p=0;p<t.length;p++)if(s[d.id]){c.outputs.forEach(g=>s[g.id]=!0),f=!0,r[c.id]=!0;break}if(f)break}}const o={};o[e.id]=!0;const i={};for(let l=n.length-1;l>=0;l--){const c=n[l],u=c.inputs;for(let h=0;h<c.outputs.length;h++)if(o[c.outputs[h].id]){for(const d in u)o[u[d].id]=!0,i[c.id]=!0;break}}const a=[];for(let l=0;l<n.length;l++){const c=n[l];if(r[c.id]&&i[c.id]){const u={};for(const d in c.inputs){const f=c.inputs[d];s[f.id]&&(u[d]=f)}const h=Object.assign({},c);h.inputs=u,h.outputs=c.outputs,a.push(h)}}return a}function Mg(n,t,e,s){for(let r=t.length-1;r>=0;r--){const o=t[r],i=[];if(o.outputs.forEach(l=>{const c=n[l.id];c!=null?i.push(c):i.push(null)}),o.gradient==null)throw new Error(`Cannot compute gradient: gradient function not found for ${o.kernelName}.`);const a=o.gradient(i);for(const l in o.inputs){if(!(l in a))throw new Error(`Cannot backprop through input ${l}. Available gradients found: ${Object.keys(a)}.`);const c=e(()=>a[l]());if(c.dtype!=="float32")throw new Error(`Error in gradient for op ${o.kernelName}. The gradient of input ${l} must have 'float32' dtype, but has '${c.dtype}'`);const u=o.inputs[l];if(!oe(c.shape,u.shape))throw new Error(`Error in gradient for op ${o.kernelName}. The gradient of input '${l}' has shape '${c.shape}', which does not match the shape of the input '${u.shape}'`);if(n[u.id]==null)n[u.id]=c;else{const h=n[u.id];n[u.id]=s(h,c),h.dispose()}}}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Nu=20,qs=3,Ua=7;function Rg(n,t,e,s){const r=it(t),o=zg(n,t,e,r),i=t.length,a=uo(n,t,e,r,o),l=["Tensor"];return s&&(l.push(`  dtype: ${e}`),l.push(`  rank: ${i}`),l.push(`  shape: [${t}]`),l.push("  values:")),l.push(a.map(c=>"    "+c).join(`
`)),l.join(`
`)}function zg(n,t,e,s){const r=Z(t),o=s[s.length-1],i=new Array(o).fill(0),a=t.length,l=e==="complex64"?Ks(n):n;if(a>1)for(let c=0;c<r/o;c++){const u=c*o;for(let h=0;h<o;h++)i[h]=Math.max(i[h],js(l[u+h],0,e).length)}return i}function js(n,t,e){let s;return Array.isArray(n)?s=`${parseFloat(n[0].toFixed(Ua))} + ${parseFloat(n[1].toFixed(Ua))}j`:Cr(n)?s=`'${n}'`:e==="bool"?s=$u(n):s=parseFloat(n.toFixed(Ua)).toString(),Tr(s,t)}function $u(n){return n===0?"false":"true"}function uo(n,t,e,s,r,o=!0){const i=e==="complex64"?2:1,a=t[0],l=t.length;if(l===0){if(e==="complex64"){const g=Ks(n);return[js(g[0],0,e)]}return e==="bool"?[$u(n[0])]:[n[0].toString()]}if(l===1){if(a>Nu){const m=qs*i;let b=Array.from(n.slice(0,m)),y=Array.from(n.slice((a-qs)*i,a*i));return e==="complex64"&&(b=Ks(b),y=Ks(y)),["["+b.map((k,w)=>js(k,r[w],e)).join(", ")+", ..., "+y.map((k,w)=>js(k,r[a-qs+w],e)).join(", ")+"]"]}return["["+(e==="complex64"?Ks(n):Array.from(n)).map((m,b)=>js(m,r[b],e)).join(", ")+"]"]}const c=t.slice(1),u=s.slice(1),h=s[0]*i,d=[];if(a>Nu){for(let g=0;g<qs;g++){const m=g*h,b=m+h;d.push(...uo(n.slice(m,b),c,e,u,r,!1))}d.push("...");for(let g=a-qs;g<a;g++){const m=g*h,b=m+h;d.push(...uo(n.slice(m,b),c,e,u,r,g===a-1))}}else for(let g=0;g<a;g++){const m=g*h,b=m+h;d.push(...uo(n.slice(m,b),c,e,u,r,g===a-1))}const f=l===2?",":"";d[0]="["+(a>0?d[0]+f:"");for(let g=1;g<d.length-1;g++)d[g]=" "+d[g]+f;let p=`,
`;for(let g=2;g<l;g++)p+=`
`;return d[d.length-1]=" "+d[d.length-1]+"]"+(o?"":p),d}function Ks(n){const t=[];for(let e=0;e<n.length;e+=2)t.push([n[e],n[e+1]]);return t}/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class te{constructor(t,e,s){if(this.dtype=e,this.shape=t.slice(),this.size=Z(t),s!=null){const r=s.length;v(r===this.size,()=>`Length of values '${r}' does not match the size inferred by the shape '${this.size}'.`)}if(e==="complex64")throw new Error("complex64 dtype TensorBuffers are not supported. Please create a TensorBuffer for the real and imaginary parts separately and call tf.complex(real, imag).");this.values=s||Gt(e,this.size),this.strides=it(t)}set(t,...e){e.length===0&&(e=[0]),v(e.length===this.rank,()=>`The number of provided coordinates (${e.length}) must match the rank (${this.rank})`);const s=this.locToIndex(e);this.values[s]=t}get(...t){t.length===0&&(t=[0]);let e=0;for(const r of t){if(r<0||r>=this.shape[e]){const o=`Requested out of range element at ${t}.   Buffer shape=${this.shape}`;throw new Error(o)}e++}let s=t[t.length-1];for(let r=0;r<t.length-1;++r)s+=this.strides[r]*t[r];return this.values[s]}locToIndex(t){if(this.rank===0)return 0;if(this.rank===1)return t[0];let e=t[t.length-1];for(let s=0;s<t.length-1;++s)e+=this.strides[s]*t[s];return e}indexToLoc(t){if(this.rank===0)return[];if(this.rank===1)return[t];const e=new Array(this.shape.length);for(let s=0;s<e.length-1;++s)e[s]=Math.floor(t/this.strides[s]),t-=e[s]*this.strides[s];return e[e.length-1]=t,e}get rank(){return this.shape.length}toTensor(){return Oe().makeTensor(this.values,this.shape,this.dtype)}}let Oe=null,ps=null;function Lg(n){Oe=n}function Og(n){ps=n}class ee{constructor(t,e,s,r){this.kept=!1,this.isDisposedInternal=!1,this.shape=t.slice(),this.dtype=e||"float32",this.size=Z(t),this.strides=it(t),this.dataId=s,this.id=r,this.rankType=this.rank<5?this.rank.toString():"higher"}get rank(){return this.shape.length}async buffer(){const t=await this.data();return ps.buffer(this.shape,this.dtype,t)}bufferSync(){return ps.buffer(this.shape,this.dtype,this.dataSync())}async array(){const t=await this.data();return Le(this.shape,t,this.dtype==="complex64")}arraySync(){return Le(this.shape,this.dataSync(),this.dtype==="complex64")}async data(){this.throwIfDisposed();const t=Oe().read(this.dataId);if(this.dtype==="string"){const e=await t;try{return e.map(s=>Us(s))}catch{throw new Error("Failed to decode the string bytes into utf-8. To get the original bytes, call tensor.bytes().")}}return t}dataToGPU(t){return this.throwIfDisposed(),Oe().readToGPU(this.dataId,t)}dataSync(){this.throwIfDisposed();const t=Oe().readSync(this.dataId);if(this.dtype==="string")try{return t.map(e=>Us(e))}catch{throw new Error("Failed to decode the string bytes into utf-8. To get the original bytes, call tensor.bytes().")}return t}async bytes(){this.throwIfDisposed();const t=await Oe().read(this.dataId);return this.dtype==="string"?t:new Uint8Array(t.buffer)}dispose(){this.isDisposed||(this.kerasMask&&this.kerasMask.dispose(),Oe().disposeTensor(this),this.isDisposedInternal=!0)}get isDisposed(){return this.isDisposedInternal}throwIfDisposed(){if(this.isDisposed)throw new Error("Tensor is disposed.")}print(t=!1){return ps.print(this,t)}clone(){return this.throwIfDisposed(),ps.clone(this)}toString(t=!1){const e=this.dataSync();return Rg(e,this.shape,this.dtype,t)}cast(t){return this.throwIfDisposed(),ps.cast(this,t)}variable(t=!0,e,s){return this.throwIfDisposed(),Oe().makeVariable(this,t,e,s)}}Object.defineProperty(ee,Symbol.hasInstance,{value:n=>!!n&&n.data!=null&&n.dataSync!=null&&n.throwIfDisposed!=null});function Tu(){return vi("Tensor",()=>ee)}Tu();class ho extends ee{constructor(t,e,s,r){super(t.shape,t.dtype,t.dataId,r),this.trainable=e,this.name=s}assign(t){if(t.dtype!==this.dtype)throw new Error(`dtype of the new value (${t.dtype}) and previous value (${this.dtype}) must match`);if(!oe(t.shape,this.shape))throw new Error(`shape of the new value (${t.shape}) and previous value (${this.shape}) must match`);Oe().disposeTensor(this),this.dataId=t.dataId,Oe().incRef(this,null)}dispose(){Oe().disposeVariable(this),this.isDisposedInternal=!0}}Object.defineProperty(ho,Symbol.hasInstance,{value:n=>n instanceof ee&&n.assign!=null&&n.assign instanceof Function});/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */var Cu;(function(n){n.R0="R0",n.R1="R1",n.R2="R2",n.R3="R3",n.R4="R4",n.R5="R5",n.R6="R6"})(Cu||(Cu={}));var Ha;(function(n){n.float32="float32",n.int32="int32",n.bool="int32",n.complex64="complex64"})(Ha||(Ha={}));var qa;(function(n){n.float32="float32",n.int32="int32",n.bool="bool",n.complex64="complex64"})(qa||(qa={}));var ja;(function(n){n.float32="float32",n.int32="float32",n.bool="float32",n.complex64="complex64"})(ja||(ja={}));var Ka;(function(n){n.float32="complex64",n.int32="complex64",n.bool="complex64",n.complex64="complex64"})(Ka||(Ka={}));const _g={float32:ja,int32:Ha,bool:qa,complex64:Ka};function ms(n,t){if(n==="string"||t==="string"){if(n==="string"&&t==="string")return"string";throw new Error(`Can not upcast ${n} with ${t}`)}return _g[n][t]}function Au(n){return n!=null&&typeof n=="object"&&"texture"in n&&n.texture instanceof WebGLTexture}function Eu(n){return typeof GPUBuffer<"u"&&n!=null&&typeof n=="object"&&"buffer"in n&&n.buffer instanceof GPUBuffer}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function ne(n,t){if(n.dtype===t.dtype)return[n,t];const e=ms(n.dtype,t.dtype);return[n.cast(e),t.cast(e)]}function Du(n){const t=[];return Fu(n,t,new Set),t}function Fu(n,t,e){if(n==null)return;if(n instanceof ee){t.push(n);return}if(!Bg(n))return;const s=n;for(const r in s){const o=s[r];e.has(o)||(e.add(o),Fu(o,t,e))}}function Bg(n){return Array.isArray(n)||typeof n=="object"}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Xa(n){return n.kernelName!=null}class Mu{constructor(){this.registeredVariables={},this.nextTapeNodeId=0,this.numBytes=0,this.numTensors=0,this.numStringTensors=0,this.numDataBuffers=0,this.gradientDepth=0,this.kernelDepth=0,this.scopeStack=[],this.numDataMovesStack=[],this.nextScopeId=0,this.tensorInfo=new WeakMap,this.profiling=!1,this.activeProfile={newBytes:0,newTensors:0,peakBytes:0,kernels:[],result:null,get kernelNames(){return Array.from(new Set(this.kernels.map(t=>t.name)))}}}dispose(){for(const t in this.registeredVariables)this.registeredVariables[t].dispose()}}class gs{constructor(t){this.ENV=t,this.registry={},this.registryFactory={},this.pendingBackendInitId=0,this.state=new Mu}async ready(){if(this.pendingBackendInit!=null)return this.pendingBackendInit.then(()=>{});if(this.backendInstance!=null)return;const t=this.getSortedBackends();for(let e=0;e<t.length;e++){const s=t[e];if(await this.initializeBackend(s).success){await this.setBackend(s);return}}throw new Error("Could not initialize any backends, all backend initializations failed.")}get backend(){if(this.pendingBackendInit!=null)throw new Error(`Backend '${this.backendName}' has not yet been initialized. Make sure to await tf.ready() or await tf.setBackend() before calling other methods`);if(this.backendInstance==null){const{name:t,asyncInit:e}=this.initializeBackendsAndReturnBest();if(e)throw new Error(`The highest priority backend '${t}' has not yet been initialized. Make sure to await tf.ready() or await tf.setBackend() before calling other methods`);this.setBackend(t)}return this.backendInstance}backendNames(){return Object.keys(this.registryFactory)}findBackend(t){if(!(t in this.registry))if(t in this.registryFactory){const{asyncInit:e}=this.initializeBackend(t);if(e)return null}else return null;return this.registry[t]}findBackendFactory(t){return t in this.registryFactory?this.registryFactory[t].factory:null}registerBackend(t,e,s=1){return t in this.registryFactory?(In(`${t} backend was already registered. Reusing existing backend factory.`),!1):(this.registryFactory[t]={factory:e,priority:s},!0)}async setBackend(t){if(this.registryFactory[t]==null)throw new Error(`Backend name '${t}' not found in registry`);if(this.backendName=t,this.registry[t]==null){this.backendInstance=null;const{success:e,asyncInit:s}=this.initializeBackend(t);if(!(s?await e:e))return!1}return this.backendInstance=this.registry[t],this.setupRegisteredKernels(),this.profiler=new Ag(this.backendInstance),!0}setupRegisteredKernels(){gu(this.backendName).forEach(e=>{e.setupFunc!=null&&e.setupFunc(this.backendInstance)})}disposeRegisteredKernels(t){gu(t).forEach(s=>{s.disposeFunc!=null&&s.disposeFunc(this.registry[t])})}initializeBackend(t){const e=this.registryFactory[t];if(e==null)throw new Error(`Cannot initialize backend ${t}, no registration found.`);try{const s=e.factory();if(s&&!(s instanceof wc)&&typeof s.then=="function"){const r=++this.pendingBackendInitId,o=s.then(i=>r<this.pendingBackendInitId?!1:(this.registry[t]=i,this.pendingBackendInit=null,!0)).catch(i=>(r<this.pendingBackendInitId||(this.pendingBackendInit=null,In(`Initialization of backend ${t} failed`),In(i.stack||i.message)),!1));return this.pendingBackendInit=o,{success:o,asyncInit:!0}}else return this.registry[t]=s,{success:!0,asyncInit:!1}}catch(s){return In(`Initialization of backend ${t} failed`),In(s.stack||s.message),{success:!1,asyncInit:!1}}}removeBackend(t){if(!(t in this.registryFactory))throw new Error(`${t} backend not found in registry`);this.backendName===t&&this.pendingBackendInit!=null&&this.pendingBackendInitId++,t in this.registry&&(this.disposeRegisteredKernels(t),this.registry[t].dispose(),delete this.registry[t]),delete this.registryFactory[t],this.backendName===t&&(this.pendingBackendInit=null,this.backendName=null,this.backendInstance=null)}getSortedBackends(){if(Object.keys(this.registryFactory).length===0)throw new Error("No backend found in registry.");return Object.keys(this.registryFactory).sort((t,e)=>this.registryFactory[e].priority-this.registryFactory[t].priority)}initializeBackendsAndReturnBest(){const t=this.getSortedBackends();for(let e=0;e<t.length;e++){const s=t[e],{success:r,asyncInit:o}=this.initializeBackend(s);if(o||r)return{name:s,asyncInit:o}}throw new Error("Could not initialize any backends, all backend initializations failed.")}moveData(t,e){const s=this.state.tensorInfo.get(e),r=s.backend,o=this.readSync(e),i=r.refCount(e);r.disposeData(e,!0),s.backend=t,t.move(e,o,s.shape,s.dtype,i),this.shouldCheckForMemLeaks()&&this.state.numDataMovesStack[this.state.numDataMovesStack.length-1]++}tidy(t,e){let s=null;if(e==null){if(typeof t!="function")throw new Error("Please provide a function to tidy()");e=t}else{if(typeof t!="string"&&!(t instanceof String))throw new Error("When calling with two arguments, the first argument to tidy() must be a string");if(typeof e!="function")throw new Error("When calling with two arguments, the 2nd argument to tidy() must be a function");s=t}let r;return this.scopedRun(()=>this.startScope(s),()=>this.endScope(r),()=>(r=e(),r instanceof Promise&&console.error("Cannot return a Promise inside of tidy."),r))}scopedRun(t,e,s){t();try{const r=s();return e(),r}catch(r){throw e(),r}}nextTensorId(){return gs.nextTensorId++}nextVariableId(){return gs.nextVariableId++}clone(t){const e=R.runKernel(Pr,{x:t}),s={x:t},r=i=>({x:()=>{const a="float32",l={x:i},c={dtype:a};return R.runKernel(Ar,l,c)}}),o=[];return this.addTapeNode(this.state.activeScope.name,s,[e],r,o,{}),e}runKernel(t,e,s){if(this.backendName==null&&this.backend,!(pu(t,this.backendName)!=null))throw new Error(`Kernel '${t}' not registered for backend '${this.backendName}'`);return this.runKernelFunc({kernelName:t,inputs:e,attrs:s})}shouldCheckForMemLeaks(){return this.ENV.getBool("IS_TEST")}checkKernelForMemLeak(t,e,s){const r=this.backend.numDataIds();let o=0;s.forEach(l=>{o+=l.dtype==="complex64"?3:1});const i=this.state.numDataMovesStack[this.state.numDataMovesStack.length-1],a=r-e-o-i;if(a>0)throw new Error(`Backend '${this.backendName}' has an internal memory leak (${a} data ids) after running '${t}'`)}runKernelFunc(t){let e,s=[];const r=this.isTapeOn(),o=this.state.numBytes,i=this.state.numTensors;this.shouldCheckForMemLeaks()&&this.state.numDataMovesStack.push(0);let a;this.backendName==null&&this.backend;let l;const c=Xa(t)?t.kernelName:this.state.activeScope!=null?this.state.activeScope.name:"";if(Xa(t)){const{kernelName:p,inputs:g,attrs:m}=t;this.backendName==null&&this.backend;const b=pu(p,this.backendName);v(b!=null,()=>`Cannot find registered kernel '${p}' for backend '${this.backendName}'`),a=()=>{const y=this.backend.numDataIds();l=b.kernelFunc({inputs:g,attrs:m,backend:this.backend});const k=Array.isArray(l)?l:[l];this.shouldCheckForMemLeaks()&&this.checkKernelForMemLeak(p,y,k);const w=k.map(I=>I.rank!=null?I:this.makeTensorFromTensorInfo(I));if(r){const I=this.getTensorsForGradient(p,g,w);s=this.saveTensorsForBackwardMode(I)}return w}}else{const{forwardFunc:p}=t,g=m=>{r&&(s=m.map(b=>this.keep(this.clone(b))))};a=()=>{const m=this.backend.numDataIds();l=this.tidy(()=>p(this.backend,g));const b=Array.isArray(l)?l:[l];return this.shouldCheckForMemLeaks()&&this.checkKernelForMemLeak(c,m,b),b}}const{inputs:u,attrs:h}=t,d=Xa(t)?null:t.backwardsFunc;let f;return this.scopedRun(()=>this.state.kernelDepth++,()=>this.state.kernelDepth--,()=>{!this.ENV.getBool("DEBUG")&&!this.state.profiling?e=a():(f=this.profiler.profileKernel(c,u,()=>a()),this.ENV.getBool("DEBUG")&&this.profiler.logKernelProfile(f),e=f.outputs)}),r&&this.addTapeNode(c,u,e,d,s,h),this.state.profiling&&this.state.activeProfile.kernels.push({name:c,bytesAdded:this.state.numBytes-o,totalBytesSnapshot:this.state.numBytes,tensorsAdded:this.state.numTensors-i,totalTensorsSnapshot:this.state.numTensors,inputShapes:Object.keys(u).map(p=>u[p]!=null?u[p].shape:null),outputShapes:e.map(p=>p.shape),kernelTimeMs:f.timeMs,extraInfo:f.extraInfo}),Array.isArray(l)?e:e[0]}saveTensorsForBackwardMode(t){return t.map(s=>this.keep(this.clone(s)))}getTensorsForGradient(t,e,s){const r=mu(t);if(r!=null){const o=r.inputsToSave||[],i=r.outputsToSave||[];let a;r.saveAllInputs?(v(Array.isArray(e),()=>"saveAllInputs is true, expected inputs to be an array."),a=Object.keys(e).map(c=>e[c])):a=o.map(c=>e[c]);const l=s.filter((c,u)=>i[u]);return a.concat(l)}return[]}makeTensor(t,e,s,r){if(t==null)throw new Error("Values passed to engine.makeTensor() are null");s=s||"float32",r=r||this.backend;let o=t;s==="string"&&Cr(t[0])&&(o=t.map(l=>Xn(l)));const i=r.write(o,e,s),a=new ee(e,s,i,this.nextTensorId());if(this.trackTensor(a,r),s==="string"){const l=this.state.tensorInfo.get(i),c=Fm(o);this.state.numBytes+=c-l.bytes,l.bytes=c}return a}makeTensorFromDataId(t,e,s,r){s=s||"float32";const o={dataId:t,shape:e,dtype:s};return this.makeTensorFromTensorInfo(o,r)}makeTensorFromTensorInfo(t,e){const{dataId:s,shape:r,dtype:o}=t,i=new ee(r,o,s,this.nextTensorId());return this.trackTensor(i,e),i}makeVariable(t,e=!0,s,r){s=s||this.nextVariableId().toString(),r!=null&&r!==t.dtype&&(t=t.cast(r));const o=new ho(t,e,s,this.nextTensorId());if(this.state.registeredVariables[o.name]!=null)throw new Error(`Variable with name ${o.name} was already registered`);return this.state.registeredVariables[o.name]=o,this.incRef(o,this.backend),o}trackTensor(t,e){this.state.numTensors++,t.dtype==="string"&&this.state.numStringTensors++;let s=0;t.dtype!=="complex64"&&t.dtype!=="string"&&(s=t.size*yi(t.dtype)),this.state.numBytes+=s,this.state.tensorInfo.has(t.dataId)||(this.state.numDataBuffers++,this.state.tensorInfo.set(t.dataId,{backend:e||this.backend,dtype:t.dtype,shape:t.shape,bytes:s})),t instanceof ho||this.track(t)}incRef(t,e){this.trackTensor(t,e),this.backend.incRef(t.dataId)}removeDataId(t,e){this.state.tensorInfo.has(t)&&this.state.tensorInfo.get(t).backend===e&&(this.state.tensorInfo.delete(t),this.state.numDataBuffers--)}disposeTensor(t){if(!this.state.tensorInfo.has(t.dataId))return;const e=this.state.tensorInfo.get(t.dataId);if(this.state.numTensors--,t.dtype==="string"&&(this.state.numStringTensors--,this.state.numBytes-=e.bytes),t.dtype!=="complex64"&&t.dtype!=="string"){const s=t.size*yi(t.dtype);this.state.numBytes-=s}e.backend.disposeData(t.dataId)&&this.removeDataId(t.dataId,e.backend)}disposeVariables(){for(const t in this.state.registeredVariables){const e=this.state.registeredVariables[t];this.disposeVariable(e)}}disposeVariable(t){this.disposeTensor(t),this.state.registeredVariables[t.name]!=null&&delete this.state.registeredVariables[t.name]}memory(){const t=this.backend.memory();return t.numTensors=this.state.numTensors,t.numDataBuffers=this.state.numDataBuffers,t.numBytes=this.state.numBytes,this.state.numStringTensors>0&&(t.unreliable=!0,t.reasons==null&&(t.reasons=[]),t.reasons.push("Memory usage by string tensors is approximate (2 bytes per character)")),t}async profile(t){this.state.profiling=!0;const e=this.state.numBytes,s=this.state.numTensors;this.state.activeProfile.kernels=[],this.state.activeProfile.result=await t(),this.state.profiling=!1,this.state.activeProfile.peakBytes=Math.max(...this.state.activeProfile.kernels.map(r=>r.totalBytesSnapshot)),this.state.activeProfile.newBytes=this.state.numBytes-e,this.state.activeProfile.newTensors=this.state.numTensors-s;for(const r of this.state.activeProfile.kernels)r.kernelTimeMs=await r.kernelTimeMs,r.extraInfo=await r.extraInfo;return this.state.activeProfile}isTapeOn(){return this.state.gradientDepth>0&&this.state.kernelDepth===0}addTapeNode(t,e,s,r,o,i){const a={id:this.state.nextTapeNodeId++,kernelName:t,inputs:e,outputs:s,saved:o},l=mu(t);l!=null&&(r=l.gradFunc),r!=null&&(a.gradient=c=>(c=c.map((u,h)=>{if(u==null){const d=s[h],f=ie(d.size,d.dtype);return this.makeTensor(f,d.shape,d.dtype)}return u}),r(c.length>1?c:c[0],o,i))),this.state.activeTape.push(a)}keep(t){return t.kept=!0,t}startTape(){this.state.gradientDepth===0&&(this.state.activeTape=[]),this.state.gradientDepth++}endTape(){this.state.gradientDepth--}startScope(t){const e={track:[],name:"unnamed scope",id:this.state.nextScopeId++};t&&(e.name=t),this.state.scopeStack.push(e),this.state.activeScope=e}endScope(t){const e=Du(t),s=new Set(e.map(o=>o.id));for(let o=0;o<this.state.activeScope.track.length;o++){const i=this.state.activeScope.track[o];!i.kept&&!s.has(i.id)&&i.dispose()}const r=this.state.scopeStack.pop();this.state.activeScope=this.state.scopeStack.length===0?null:this.state.scopeStack[this.state.scopeStack.length-1],e.forEach(o=>{!o.kept&&o.scopeId===r.id&&this.track(o)})}gradients(t,e,s,r=!1){if(v(e.length>0,()=>"gradients() received an empty list of xs."),s!=null&&s.dtype!=="float32")throw new Error(`dy must have 'float32' dtype, but has '${s.dtype}'`);const o=this.scopedRun(()=>this.startTape(),()=>this.endTape(),()=>this.tidy("forward",t));v(o instanceof ee,()=>"The result y returned by f() must be a tensor.");const i=Fg(this.state.activeTape,e,o);if(!r&&i.length===0&&e.length>0)throw new Error("Cannot compute gradient of y=f(x) with respect to x. Make sure that the f you passed encloses all operations that lead from x to y.");return this.tidy("backward",()=>{const a={};a[o.id]=s??Pg(o.shape),Mg(a,i,c=>this.tidy(c),Wg);const l=e.map(c=>a[c.id]);return this.state.gradientDepth===0&&(this.state.activeTape.forEach(c=>{for(const u of c.saved)u.dispose()}),this.state.activeTape=null),{value:o,grads:l}})}customGrad(t){return v(ki(t),()=>"The f passed in customGrad(f) must be a function."),(...e)=>{v(e.every(a=>a instanceof ee),()=>"The args passed in customGrad(f)(x1, x2,...) must all be tensors");let s;const r={};e.forEach((a,l)=>{r[l]=a});const o=(a,l)=>(s=t(...e,l),v(s.value instanceof ee,()=>"The function f passed in customGrad(f) must return an object where `obj.value` is a tensor"),v(ki(s.gradFunc),()=>"The function f passed in customGrad(f) must return an object where `obj.gradFunc` is a function."),s.value),i=(a,l)=>{const c=s.gradFunc(a,l),u=Array.isArray(c)?c:[c];v(u.length===e.length,()=>"The function f passed in customGrad(f) must return an object where `obj.gradFunc` is a function that returns the same number of tensors as inputs passed to f(...)."),v(u.every(d=>d instanceof ee),()=>"The function f passed in customGrad(f) must return an object where `obj.gradFunc` is a function that returns a list of only tensors.");const h={};return u.forEach((d,f)=>{h[f]=()=>d}),h};return this.runKernelFunc({forwardFunc:o,backwardsFunc:i,inputs:r})}}readSync(t){return this.state.tensorInfo.get(t).backend.readSync(t)}read(t){return this.state.tensorInfo.get(t).backend.read(t)}readToGPU(t,e){return this.state.tensorInfo.get(t).backend.readToGPU(t,e)}async time(t){const e=vn(),s=await this.backend.time(t);return s.wallMs=vn()-e,s}track(t){return this.state.activeScope!=null&&(t.scopeId=this.state.activeScope.id,this.state.activeScope.track.push(t)),t}get registeredVariables(){return this.state.registeredVariables}reset(){this.pendingBackendInitId++,this.state.dispose(),this.ENV.reset(),this.state=new Mu;for(const t in this.registry)this.disposeRegisteredKernels(t),this.registry[t].dispose(),delete this.registry[t];this.backendName=null,this.backendInstance=null,this.pendingBackendInit=null}}gs.nextTensorId=0,gs.nextVariableId=0;function Pg(n){const t=xi(Z(n),"float32");return R.makeTensor(t,n,"float32")}function Ru(){const n=$c();if(n._tfengine==null){const t=new zm(n);n._tfengine=new gs(t)}return Bm(n._tfengine.ENV),Lg(()=>n._tfengine),n._tfengine}const R=Ru();function Wg(n,t){const e={a:n,b:t};return R.runKernel(Vs,e)}/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Vg(){return typeof window<"u"&&window.document!=null||typeof WorkerGlobalScope<"u"}/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const de=gt();de.registerFlag("DEBUG",()=>!1,n=>{n&&console.warn("Debugging mode is ON. The output of every math call will be downloaded to CPU and checked for NaNs. This significantly impacts performance.")}),de.registerFlag("IS_BROWSER",()=>Vg()),de.registerFlag("IS_NODE",()=>typeof process<"u"&&typeof process.versions<"u"&&typeof process.versions.node<"u"),de.registerFlag("IS_CHROME",()=>typeof navigator<"u"&&navigator!=null&&navigator.userAgent!=null&&/Chrome/.test(navigator.userAgent)&&/Google Inc/.test(navigator.vendor)),de.registerFlag("IS_SAFARI",()=>typeof navigator<"u"&&navigator!=null&&navigator.userAgent!=null&&/Safari/.test(navigator.userAgent)&&/Apple/.test(navigator.vendor)),de.registerFlag("PROD",()=>!1),de.registerFlag("TENSORLIKE_CHECK_SHAPE_CONSISTENCY",()=>de.getBool("DEBUG")),de.registerFlag("DEPRECATION_WARNINGS_ENABLED",()=>!0),de.registerFlag("IS_TEST",()=>!1),de.registerFlag("CHECK_COMPUTATION_FOR_ERRORS",()=>de.getBool("DEBUG")),de.registerFlag("WRAP_TO_IMAGEBITMAP",()=>!1),de.registerFlag("CANVAS2D_WILL_READ_FREQUENTLY_FOR_GPU",()=>!1),de.registerFlag("USE_SETTIMEOUTCUSTOM",()=>!1);/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function fo(n,t){let e=n;if(Ne(n))return t==="string"?[]:[n.length];if(Au(n)){const r=n.channels||"RGBA";return[n.height,n.width*r.length]}else if(Eu(n))return[n.buffer.size/(t==null?4:yi(t))];if(!Array.isArray(n))return[];const s=[];for(;Array.isArray(e)||Ne(e)&&t!=="string";)s.push(e.length),e=e[0];return Array.isArray(n)&&gt().getBool("TENSORLIKE_CHECK_SHAPE_CONSISTENCY")&&zu(n,s,[]),s}function zu(n,t,e){if(e=e||[],!Array.isArray(n)&&!Ne(n)){v(t.length===0,()=>`Element arr[${e.join("][")}] is a primitive, but should be an array/TypedArray of ${t[0]} elements`);return}v(t.length>0,()=>`Element arr[${e.join("][")}] should be a primitive, but is an array of ${n.length} elements`),v(n.length===t[0],()=>`Element arr[${e.join("][")}] should have ${t[0]} elements, but has ${n.length} elements`);const s=t.slice(1);for(let r=0;r<n.length;++r)zu(n[r],s,e.concat(r))}function Lu(n,t,e,s){if(n!=="string_or_numeric"){if(n==null)throw new Error("Expected dtype cannot be null.");if(n!=="numeric"&&n!==t||n==="numeric"&&t==="string")throw new Error(`Argument '${e}' passed to '${s}' must be ${n} tensor, but got ${t} tensor`)}}function E(n,t,e,s="numeric"){if(n instanceof Tu())return Lu(s,n.dtype,t,e),n;let r=Ws(n);if(r!=="string"&&["bool","int32","float32"].indexOf(s)>=0&&(r=s),Lu(s,r,t,e),n==null||!Ne(n)&&!Array.isArray(n)&&typeof n!="number"&&typeof n!="boolean"&&typeof n!="string"){const l=n==null?"null":n.constructor.name;throw new Error(`Argument '${t}' passed to '${e}' must be a Tensor or TensorLike, but got '${l}'`)}const o=fo(n,r);!Ne(n)&&!Array.isArray(n)&&(n=[n]);const a=r!=="string"?Kn(n,r):Hs(n,[],!0);return R.makeTensor(a,o,r)}function Ou(n,t,e,s="numeric"){if(!Array.isArray(n))throw new Error(`Argument ${t} passed to ${e} must be a \`Tensor[]\` or \`TensorLike[]\``);return n.map((o,i)=>E(o,`${t}[${i}]`,e,s))}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Gg="__op";function P(n){const t=Object.keys(n);if(t.length!==1)throw new Error(`Please provide an object with a single key (operation name) mapping to a function. Got an object with ${t.length} keys.`);let e=t[0];const s=n[e];e.endsWith("_")&&(e=e.substring(0,e.length-1)),e=e+Gg;const r=(...o)=>{R.startScope(e);try{const i=s(...o);return Ii(i)&&console.error("Cannot return a Promise inside of tidy."),R.endScope(i),i}catch(i){throw R.endScope(null),i}};return Object.defineProperty(r,"name",{value:e,configurable:!0}),r}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ug(n,t){const e=E(n,"real","complex"),s=E(t,"imag","complex");kc(e.shape,s.shape,`real and imag shapes, ${e.shape} and ${s.shape}, must match in call to tf.complex().`);const r={real:e,imag:s};return R.runKernel(zc,r)}const po=P({complex_:Ug});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function mo(n,t,e,s){if(s==null)s=Ws(n);else if(s==="complex64")throw new Error("Cannot construct a complex64 tensor directly. Please use tf.complex(real, imag).");if(Eu(n)||Au(n)){if(s!=="float32"&&s!=="int32")throw new Error(`Creating tensor from GPU data only supports 'float32'|'int32' dtype, while the dtype is ${s}.`);return R.backend.createTensorFromGPUData(n,t||e,s)}if(!Ne(n)&&!Array.isArray(n)&&typeof n!="number"&&typeof n!="boolean"&&typeof n!="string")throw new Error("values passed to tensor(values) must be a number/boolean/string or an array of numbers/booleans/strings, or a TypedArray");if(t!=null){dn(t);const r=Z(t),o=Z(e);v(r===o,()=>`Based on the provided shape, [${t}], the tensor should have ${r} values but has ${o}`);for(let i=0;i<e.length;++i){const a=e[i],l=i===e.length-1?a!==Z(t.slice(i)):!0;v(e[i]===t[i]||!l,()=>`Error creating a new Tensor. Inferred shape (${e}) does not match the provided shape (${t}). `)}}return!Ne(n)&&!Array.isArray(n)&&(n=[n]),t=t||e,n=s!=="string"?Kn(n,s):Hs(n,[],!0),R.makeTensor(n,t,s)}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Xs(n,t,e){const s=fo(n,e);return mo(n,t,s,e)}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const go={float32:4,float16:2,int32:4,uint16:2,uint8:1,bool:1,complex64:8};class Nn{static join(t){return new Nn(t).slice()}constructor(t){if(this.shards=[],this.previousShardIndex=0,t==null||(t instanceof Array||(t=[t]),t=t.map(s=>Ne(s)?s.buffer:s),t.length===0))return;this.bufferUniformSize=t[0].byteLength;let e=0;for(let s=0;s<t.length;s++){const r=t[s];s!==t.length-1&&r.byteLength!==this.bufferUniformSize&&(this.bufferUniformSize=void 0);const o=e+r.byteLength;this.shards.push({buffer:r,start:e,end:o}),e=o}this.shards.length===0&&(this.byteLength=0),this.byteLength=this.shards[this.shards.length-1].end}slice(t=0,e=this.byteLength){if(this.shards.length===0)return new ArrayBuffer(0);if(t=isNaN(Number(t))?0:t,e=isNaN(Number(e))?0:e,t=Math.max(0,t),e=Math.min(this.byteLength,e),e<=t)return new ArrayBuffer(0);const s=this.findShardForByte(t);if(s===-1)throw new Error(`Could not find start shard for byte ${t}`);const r=e-t,o=new ArrayBuffer(r),i=new Uint8Array(o);let a=0;for(let l=s;l<this.shards.length;l++){const c=this.shards[l],h=t+a-c.start,d=a,p=Math.min(e,c.end)-c.start,g=new Uint8Array(c.buffer,h,p-h);if(i.set(g,d),a+=g.length,e<c.end)break}return o}findShardForByte(t){if(this.shards.length===0||t<0||t>=this.byteLength)return-1;if(this.bufferUniformSize!=null)return this.previousShardIndex=Math.floor(t/this.bufferUniformSize),this.previousShardIndex;function e(r){return t<r.start?-1:t>=r.end?1:0}if(e(this.shards[this.previousShardIndex])===0)return this.previousShardIndex;const s=Hg(this.shards,e);return s===-1?-1:(this.previousShardIndex=s,this.previousShardIndex)}}function Hg(n,t){let e=0,s=n.length;for(;e<=s;){const r=Math.floor((s-e)/2)+e,o=t(n[r]);if(o===0)return r;o<0?s=r:e=r+1}return-1}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function _u(){return R}function Bu(){return R.memory()}function z(n,t){return R.tidy(n,t)}function dt(n){Du(n).forEach(e=>e.dispose())}function Ke(n){return R.keep(n)}function qg(n){return R.setBackend(n)}function jg(){return R.ready()}function Kg(n,t,e=1){return R.registerBackend(n,t,e)}function Xg(){return R.backend}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const bs=4;async function Pu(n,t){const e=[],s=[],r=Array.isArray(n)?n.map(i=>i.name):Object.keys(n);for(let i=0;i<r.length;++i){const a=r[i],l=Array.isArray(n)?n[i].tensor:n[a];if(l.dtype!=="float32"&&l.dtype!=="int32"&&l.dtype!=="bool"&&l.dtype!=="string"&&l.dtype!=="complex64")throw new Error(`Unsupported dtype in weight '${a}': ${l.dtype}`);const c={name:a,shape:l.shape,dtype:l.dtype};if(l.dtype==="string"){const u=new Promise(async h=>{const d=await l.bytes(),f=d.reduce((m,b)=>m+b.length,0)+bs*d.length,p=new Uint8Array(f);let g=0;for(let m=0;m<d.length;m++){const b=d[m],y=new Uint8Array(new Uint32Array([b.length]).buffer);p.set(y,g),g+=bs,p.set(b,g),g+=b.length}h(p)});s.push(u)}else s.push(l.data());t!=null&&(c.group=t),e.push(c)}const o=await Promise.all(s);return{data:Qg(o),specs:e}}function Zg(n,t){const e=new Nn(n),s={};let r=0;for(const o of t){const i=Jg(o,(a,l)=>e.slice(r+a,r+l));s[o.name]=Yg(o,e.slice(r,r+i)),r+=i}return s}function Jg(n,t){const e=Z(n.shape);let s;if("quantization"in n){const r=n.quantization;s=go[r.dtype]}else if(n.dtype==="string"){let r=0;for(let o=0;o<e;o++)r+=bs+new Uint32Array(t(r,r+bs))[0];return r}else s=go[n.dtype];return e*s}function Yg(n,t){const e=n.name,s=n.dtype,r=n.shape,o=Z(r);let i,a=0;if("quantization"in n){const l=n.quantization;if(l.dtype==="uint8"||l.dtype==="uint16"){if(!("min"in l&&"scale"in l))throw new Error(`Weight ${n.name} with quantization ${l.dtype} doesn't have corresponding metadata min and scale.`)}else if(l.dtype==="float16"){if(s!=="float32")throw new Error(`Weight ${n.name} is quantized with ${l.dtype} which only supports weights of type float32 not ${s}.`)}else throw new Error(`Weight ${n.name} has unknown quantization dtype ${l.dtype}. Supported quantization dtypes are: 'uint8', 'uint16', and 'float16'.`);const c=go[l.dtype],u=l.dtype==="uint8"?new Uint8Array(t):new Uint16Array(t);if(s==="float32")if(l.dtype==="uint8"||l.dtype==="uint16"){i=new Float32Array(u.length);for(let h=0;h<u.length;h++){const d=u[h];i[h]=d*l.scale+l.min}}else if(l.dtype==="float16")i=cb()(u);else throw new Error(`Unsupported quantization type ${l.dtype} for weight type float32.`);else if(s==="int32"){if(l.dtype!=="uint8"&&l.dtype!=="uint16")throw new Error(`Unsupported quantization type ${l.dtype} for weight type int32.`);i=new Int32Array(u.length);for(let h=0;h<u.length;h++){const d=u[h];i[h]=Math.round(d*l.scale+l.min)}}else throw new Error(`Unsupported dtype in weight '${e}': ${s}`);a+=o*c}else if(s==="string"){const l=Z(n.shape);i=[];for(let c=0;c<l;c++){const u=new Uint32Array(t.slice(a,a+bs))[0];a+=bs;const h=new Uint8Array(t.slice(a,a+u));i.push(h),a+=u}}else{const l=go[s];if(s==="float32")i=new Float32Array(t);else if(s==="int32")i=new Int32Array(t);else if(s==="bool")i=new Uint8Array(t);else if(s==="complex64"){i=new Float32Array(t);const c=new Float32Array(i.length/2),u=new Float32Array(i.length/2);for(let p=0;p<c.length;p++)c[p]=i[p*2],u[p]=i[p*2+1];const h=Xs(c,r,"float32"),d=Xs(u,r,"float32"),f=po(h,d);return h.dispose(),d.dispose(),f}else throw new Error(`Unsupported dtype in weight '${e}': ${s}`);a+=o*l}return Xs(i,r,s)}function Qg(n){if(n===null)throw new Error(`Invalid input value: ${JSON.stringify(n)}`);let t=0;const e=[];n.forEach(o=>{if(t+=o.byteLength,e.push(o.byteLength===o.buffer.byteLength?o:new o.constructor(o)),!(o instanceof Float32Array||o instanceof Int32Array||o instanceof Uint8Array))throw new Error(`Unsupported TypedArray subtype: ${o.constructor.name}`)});const s=new Uint8Array(t);let r=0;return e.forEach(o=>{s.set(new Uint8Array(o.buffer),r),r+=o.byteLength}),s.buffer}const Za=typeof Buffer<"u"&&(typeof Blob>"u"||typeof atob>"u"||typeof btoa>"u");function Wu(n){return Za?Buffer.byteLength(n,"utf8"):new Blob([n]).size}function tb(n){if(Za)return Buffer.from(n).toString("base64");const t=new Uint8Array(n);let e="";for(let s=0,r=t.length;s<r;s++)e+=String.fromCharCode(t[s]);return btoa(e)}function eb(n){if(Za){const s=Buffer.from(n,"base64");return s.buffer.slice(s.byteOffset,s.byteOffset+s.byteLength)}const t=atob(n),e=new Uint8Array(t.length);for(let s=0;s<t.length;++s)e.set([t.charCodeAt(s)],s);return e.buffer}function nb(n){return Nn.join(n)}function sb(n,t){const e={modelTopology:n.modelTopology,format:n.format,generatedBy:n.generatedBy,convertedBy:n.convertedBy,weightsManifest:t};return n.signature!=null&&(e.signature=n.signature),n.userDefinedMetadata!=null&&(e.userDefinedMetadata=n.userDefinedMetadata),n.modelInitializer!=null&&(e.modelInitializer=n.modelInitializer),n.initializerSignature!=null&&(e.initializerSignature=n.initializerSignature),n.trainingConfig!=null&&(e.trainingConfig=n.trainingConfig),e}function rb(n,t,e){const s={modelTopology:n.modelTopology,format:n.format,generatedBy:n.generatedBy,convertedBy:n.convertedBy};if(n.trainingConfig!=null&&(s.trainingConfig=n.trainingConfig),n.weightsManifest!=null){if(!t)throw new Error("modelJSON has weightsManifest but weightSpecs is null");if(!e)throw new Error("modelJSON has weightsManifest but weightData is null");s.weightSpecs=t,s.weightData=e}return n.signature!=null&&(s.signature=n.signature),n.userDefinedMetadata!=null&&(s.userDefinedMetadata=n.userDefinedMetadata),n.modelInitializer!=null&&(s.modelInitializer=n.modelInitializer),n.initializerSignature!=null&&(s.initializerSignature=n.initializerSignature),s}async function ob(n,t){let e,s;return n.weightsManifest!=null&&([e,s]=await t(n.weightsManifest)),rb(n,e,s)}function Ja(n){if(n.modelTopology instanceof ArrayBuffer)throw new Error("Expected JSON model topology, received ArrayBuffer.");return{dateSaved:new Date,modelTopologyType:"JSON",modelTopologyBytes:n.modelTopology==null?0:Wu(JSON.stringify(n.modelTopology)),weightSpecsBytes:n.weightSpecs==null?0:Wu(JSON.stringify(n.weightSpecs)),weightDataBytes:n.weightData==null?0:new Nn(n.weightData).byteLength}}function Vu(n){const t=[];for(const e of n)t.push(...e.weights);return t}function ib(){const n=e=>{let s=e<<13,r=0;for(;(s&8388608)===0;)r-=8388608,s<<=1;return s&=-8388609,r+=947912704,s|r},t=new Uint32Array(2048);t[0]=0;for(let e=1;e<1024;e++)t[e]=n(e);for(let e=1024;e<2048;e++)t[e]=939524096+(e-1024<<13);return t}function ab(){const n=new Uint32Array(64);n[0]=0,n[31]=1199570944,n[32]=2147483648,n[63]=3347054592;for(let t=1;t<31;t++)n[t]=t<<23;for(let t=33;t<63;t++)n[t]=2147483648+(t-32<<23);return n}function lb(){const n=new Uint32Array(64);for(let t=0;t<64;t++)n[t]=1024;return n[0]=n[32]=0,n}function cb(){const n=ib(),t=ab(),e=lb();return s=>{const r=new ArrayBuffer(4*s.length),o=new Uint32Array(r);for(let i=0;i<s.length;i++){const a=s[i],l=n[e[a>>10]+(a&1023)]+t[a>>10];o[i]=l}return new Float32Array(r)}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class Jt{constructor(){this.saveRouters=[],this.loadRouters=[]}static getInstance(){return Jt.instance==null&&(Jt.instance=new Jt),Jt.instance}static registerSaveRouter(t){Jt.getInstance().saveRouters.push(t)}static registerLoadRouter(t){Jt.getInstance().loadRouters.push(t)}static getSaveHandlers(t){return Jt.getHandlers(t,"save")}static getLoadHandlers(t,e){return Jt.getHandlers(t,"load",e)}static getHandlers(t,e,s){const r=[];return(e==="load"?Jt.getInstance().loadRouters:Jt.getInstance().saveRouters).forEach(i=>{const a=i(t,s);a!==null&&r.push(a)}),r}}const ub=n=>Jt.getSaveHandlers(n),hb=(n,t)=>Jt.getLoadHandlers(n,t);/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Ya="tensorflowjs",Qa=1,Zn="models_store",$n="model_info_store";function Gu(){if(!gt().getBool("IS_BROWSER"))throw new Error("Failed to obtain IndexedDB factory because the current environmentis not a web browser.");const n=typeof window>"u"?self:window,t=n.indexedDB||n.mozIndexedDB||n.webkitIndexedDB||n.msIndexedDB||n.shimIndexedDB;if(t==null)throw new Error("The current browser does not appear to support IndexedDB.");return t}function tl(n){const t=n.result;t.createObjectStore(Zn,{keyPath:"modelPath"}),t.createObjectStore($n,{keyPath:"modelPath"})}class Jn{constructor(t){if(this.indexedDB=Gu(),t==null||!t)throw new Error("For IndexedDB, modelPath must not be null, undefined or empty.");this.modelPath=t}async save(t){if(t.modelTopology instanceof ArrayBuffer)throw new Error("BrowserLocalStorage.save() does not support saving model topology in binary formats yet.");return this.databaseAction(this.modelPath,t)}async load(){return this.databaseAction(this.modelPath)}databaseAction(t,e){return new Promise((s,r)=>{const o=this.indexedDB.open(Ya,Qa);o.onupgradeneeded=()=>tl(o),o.onsuccess=()=>{const i=o.result;if(e==null){const a=i.transaction(Zn,"readonly"),c=a.objectStore(Zn).get(this.modelPath);c.onsuccess=()=>{if(c.result==null)return i.close(),r(new Error(`Cannot find model with path '${this.modelPath}' in IndexedDB.`));s(c.result.modelArtifacts)},c.onerror=u=>(i.close(),r(c.error)),a.oncomplete=()=>i.close()}else{e.weightData=Nn.join(e.weightData);const a=Ja(e),l=i.transaction($n,"readwrite");let c=l.objectStore($n),u;try{u=c.put({modelPath:this.modelPath,modelArtifactsInfo:a})}catch(d){return r(d)}let h;u.onsuccess=()=>{h=i.transaction(Zn,"readwrite");const d=h.objectStore(Zn);let f;try{f=d.put({modelPath:this.modelPath,modelArtifacts:e,modelArtifactsInfo:a})}catch(p){return r(p)}f.onsuccess=()=>s({modelArtifactsInfo:a}),f.onerror=p=>{c=l.objectStore($n);const g=c.delete(this.modelPath);g.onsuccess=()=>(i.close(),r(f.error)),g.onerror=m=>(i.close(),r(f.error))}},u.onerror=d=>(i.close(),r(u.error)),l.oncomplete=()=>{h==null?i.close():h.oncomplete=()=>i.close()}}},o.onerror=i=>r(o.error)})}}Jn.URL_SCHEME="indexeddb://";const Uu=n=>gt().getBool("IS_BROWSER")&&!Array.isArray(n)&&n.startsWith(Jn.URL_SCHEME)?db(n.slice(Jn.URL_SCHEME.length)):null;Jt.registerSaveRouter(Uu),Jt.registerLoadRouter(Uu);function db(n){return new Jn(n)}function fb(n){return n.startsWith(Jn.URL_SCHEME)?n.slice(Jn.URL_SCHEME.length):n}class pb{constructor(){this.indexedDB=Gu()}async listModels(){return new Promise((t,e)=>{const s=this.indexedDB.open(Ya,Qa);s.onupgradeneeded=()=>tl(s),s.onsuccess=()=>{const r=s.result,o=r.transaction($n,"readonly"),a=o.objectStore($n).getAll();a.onsuccess=()=>{const l={};for(const c of a.result)l[c.modelPath]=c.modelArtifactsInfo;t(l)},a.onerror=l=>(r.close(),e(a.error)),o.oncomplete=()=>r.close()},s.onerror=r=>e(s.error)})}async removeModel(t){return t=fb(t),new Promise((e,s)=>{const r=this.indexedDB.open(Ya,Qa);r.onupgradeneeded=()=>tl(r),r.onsuccess=()=>{const o=r.result,i=o.transaction($n,"readwrite"),a=i.objectStore($n),l=a.get(t);let c;l.onsuccess=()=>{if(l.result==null)return o.close(),s(new Error(`Cannot find model with path '${t}' in IndexedDB.`));{const u=a.delete(t),h=()=>{c=o.transaction(Zn,"readwrite");const f=c.objectStore(Zn).delete(t);f.onsuccess=()=>e(l.result.modelArtifactsInfo),f.onerror=p=>s(l.error)};u.onsuccess=h,u.onerror=d=>(h(),o.close(),s(l.error))}},l.onerror=u=>(o.close(),s(l.error)),i.oncomplete=()=>{c==null?o.close():c.oncomplete=()=>o.close()}},r.onerror=o=>s(r.error)})}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const fn="/",ys="tensorflowjs_models",Hu="info",mb="model_topology",gb="weight_specs",bb="weight_data",yb="model_metadata";function qu(n){return{info:[ys,n,Hu].join(fn),topology:[ys,n,mb].join(fn),weightSpecs:[ys,n,gb].join(fn),weightData:[ys,n,bb].join(fn),modelMetadata:[ys,n,yb].join(fn)}}function ju(n){for(const t of Object.values(n))window.localStorage.removeItem(t)}function wb(n){const t=n.split(fn);if(t.length<3)throw new Error(`Invalid key format: ${n}`);return t.slice(1,t.length-1).join(fn)}function kb(n){return n.startsWith(Yn.URL_SCHEME)?n.slice(Yn.URL_SCHEME.length):n}class Yn{constructor(t){if(!gt().getBool("IS_BROWSER")||typeof window>"u"||typeof window.localStorage>"u")throw new Error("The current environment does not support local storage.");if(this.LS=window.localStorage,t==null||!t)throw new Error("For local storage, modelPath must not be null, undefined or empty.");this.modelPath=t,this.keys=qu(this.modelPath)}async save(t){if(t.modelTopology instanceof ArrayBuffer)throw new Error("BrowserLocalStorage.save() does not support saving model topology in binary formats yet.");{const e=JSON.stringify(t.modelTopology),s=JSON.stringify(t.weightSpecs),r=Ja(t),o=Nn.join(t.weightData);try{this.LS.setItem(this.keys.info,JSON.stringify(r)),this.LS.setItem(this.keys.topology,e),this.LS.setItem(this.keys.weightSpecs,s),this.LS.setItem(this.keys.weightData,tb(o));const i={format:t.format,generatedBy:t.generatedBy,convertedBy:t.convertedBy,signature:t.signature!=null?t.signature:void 0,userDefinedMetadata:t.userDefinedMetadata!=null?t.userDefinedMetadata:void 0,modelInitializer:t.modelInitializer!=null?t.modelInitializer:void 0,initializerSignature:t.initializerSignature!=null?t.initializerSignature:void 0,trainingConfig:t.trainingConfig!=null?t.trainingConfig:void 0};return this.LS.setItem(this.keys.modelMetadata,JSON.stringify(i)),{modelArtifactsInfo:r}}catch{throw ju(this.keys),new Error(`Failed to save model '${this.modelPath}' to local storage: size quota being exceeded is a possible cause of this failure: modelTopologyBytes=${r.modelTopologyBytes}, weightSpecsBytes=${r.weightSpecsBytes}, weightDataBytes=${r.weightDataBytes}.`)}}}async load(){const t=JSON.parse(this.LS.getItem(this.keys.info));if(t==null)throw new Error(`In local storage, there is no model with name '${this.modelPath}'`);if(t.modelTopologyType!=="JSON")throw new Error("BrowserLocalStorage does not support loading non-JSON model topology yet.");const e={},s=JSON.parse(this.LS.getItem(this.keys.topology));if(s==null)throw new Error(`In local storage, the topology of model '${this.modelPath}' is missing.`);e.modelTopology=s;const r=JSON.parse(this.LS.getItem(this.keys.weightSpecs));if(r==null)throw new Error(`In local storage, the weight specs of model '${this.modelPath}' are missing.`);e.weightSpecs=r;const o=this.LS.getItem(this.keys.modelMetadata);if(o!=null){const a=JSON.parse(o);e.format=a.format,e.generatedBy=a.generatedBy,e.convertedBy=a.convertedBy,a.signature!=null&&(e.signature=a.signature),a.userDefinedMetadata!=null&&(e.userDefinedMetadata=a.userDefinedMetadata),a.modelInitializer!=null&&(e.modelInitializer=a.modelInitializer),a.initializerSignature!=null&&(e.initializerSignature=a.initializerSignature),a.trainingConfig!=null&&(e.trainingConfig=a.trainingConfig)}const i=this.LS.getItem(this.keys.weightData);if(i==null)throw new Error(`In local storage, the binary weight values of model '${this.modelPath}' are missing.`);return e.weightData=eb(i),e}}Yn.URL_SCHEME="localstorage://";const Ku=n=>gt().getBool("IS_BROWSER")&&!Array.isArray(n)&&n.startsWith(Yn.URL_SCHEME)?xb(n.slice(Yn.URL_SCHEME.length)):null;Jt.registerSaveRouter(Ku),Jt.registerLoadRouter(Ku);function xb(n){return new Yn(n)}class Ib{constructor(){v(gt().getBool("IS_BROWSER"),()=>"Current environment is not a web browser"),v(typeof window>"u"||typeof window.localStorage<"u",()=>"Current browser does not appear to support localStorage"),this.LS=window.localStorage}async listModels(){const t={},e=ys+fn,s=fn+Hu;for(let r=0;r<this.LS.length;++r){const o=this.LS.key(r);if(o.startsWith(e)&&o.endsWith(s)){const i=wb(o);t[i]=JSON.parse(this.LS.getItem(o))}}return t}async removeModel(t){t=kb(t);const e=qu(t);if(this.LS.getItem(e.info)==null)throw new Error(`Cannot find model at path '${t}'`);const s=JSON.parse(this.LS.getItem(e.info));return ju(e),s}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Xu="://";class Xe{constructor(){this.managers={}}static getInstance(){return Xe.instance==null&&(Xe.instance=new Xe),Xe.instance}static registerManager(t,e){v(t!=null,()=>"scheme must not be undefined or null."),t.endsWith(Xu)&&(t=t.slice(0,t.indexOf(Xu))),v(t.length>0,()=>"scheme must not be an empty string.");const s=Xe.getInstance();v(s.managers[t]==null,()=>`A model store manager is already registered for scheme '${t}'.`),s.managers[t]=e}static getManager(t){const e=Xe.getInstance().managers[t];if(e==null)throw new Error(`Cannot find model manager for scheme '${t}'`);return e}static getSchemes(){return Object.keys(Xe.getInstance().managers)}}/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class Sb{constructor(){this.messageName="setTimeoutCustom",this.functionRefs=[],this.handledMessageCount=0,this.hasEventListener=!1}fetch(t,e){return fetch(t,e)}now(){return performance.now()}encode(t,e){if(e!=="utf-8"&&e!=="utf8")throw new Error(`Browser's encoder only supports utf-8, but got ${e}`);return this.textEncoder==null&&(this.textEncoder=new TextEncoder),this.textEncoder.encode(t)}decode(t,e){return new TextDecoder(e).decode(t)}setTimeoutCustom(t,e){if(typeof window>"u"||!gt().getBool("USE_SETTIMEOUTCUSTOM")){setTimeout(t,e);return}this.functionRefs.push(t),setTimeout(()=>{window.postMessage({name:this.messageName,index:this.functionRefs.length-1},"*")},e),this.hasEventListener||(this.hasEventListener=!0,window.addEventListener("message",s=>{if(s.source===window&&s.data.name===this.messageName){s.stopPropagation();const r=this.functionRefs[s.data.index];r(),this.handledMessageCount++,this.handledMessageCount===this.functionRefs.length&&(this.functionRefs=[],this.handledMessageCount=0)}},!0))}isTypedArray(t){return yu(t)}}if(gt().get("IS_BROWSER")){gt().setPlatform("browser",new Sb);try{Xe.registerManager(Yn.URL_SCHEME,new Ib)}catch{}try{Xe.registerManager(Jn.URL_SCHEME,new pb)}catch{}}/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const vb={importFetch:()=>require("node-fetch")};let el;class Nb{constructor(){this.util=require("util"),this.textEncoder=new this.util.TextEncoder}fetch(t,e){return gt().global.fetch!=null?gt().global.fetch(t,e):(el==null&&(el=vb.importFetch()),el(t,e))}now(){const t=process.hrtime();return t[0]*1e3+t[1]/1e6}encode(t,e){if(e!=="utf-8"&&e!=="utf8")throw new Error(`Node built-in encoder only supports utf-8, but got ${e}`);return this.textEncoder.encode(t)}decode(t,e){return t.length===0?"":new this.util.TextDecoder(e).decode(t)}isTypedArray(t){return this.util.types.isFloat32Array(t)||this.util.types.isInt32Array(t)||this.util.types.isUint8Array(t)||this.util.types.isUint8ClampedArray(t)}}gt().get("IS_NODE")&&!gt().get("IS_BROWSER")&&gt().setPlatform("node",new Nb);/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function mt(n,t="float32",e){return t=t||"float32",dn(n),new te(n,t,e)}/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function $b(n,t){const e=E(n,"x","cast");if(!Em(t))throw new Error(`Failed to cast to unknown dtype ${t}`);if(t==="string"&&e.dtype!=="string"||t!=="string"&&e.dtype==="string")throw new Error("Only strings can be casted to strings");const s={x:e},r={dtype:t};return R.runKernel(Ar,s,r)}const Q=P({cast_:$b});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Tb(n){const e={x:E(n,"x","clone","string_or_numeric")};return R.runKernel(Pr,e)}const Qn=P({clone_:Tb});/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Cb(n,t=!1){console.log(n.toString(t))}/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */Ru(),Og({buffer:mt,cast:Q,clone:Qn,print:Cb});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ab(n,t){let e=E(n,"a","add"),s=E(t,"b","add");[e,s]=ne(e,s);const r={a:e,b:s};return R.runKernel(Vs,r)}const X=P({add_:Ab});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Eb(n,t){let e=E(n,"a","floorDiv"),s=E(t,"b","floorDiv");[e,s]=ne(e,s);const r={a:e,b:s};return R.runKernel(_r,r)}const Db=P({floorDiv_:Eb});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Fb(n,t){let e=E(n,"a","div"),s=E(t,"b","div");if([e,s]=ne(e,s),e.dtype==="int32"&&s.dtype==="int32")return Db(e,s);const r={a:e,b:s},o={};return R.runKernel(Mr,r,o)}const rt=P({div_:Fb});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Mb(n,t){let e=E(n,"a","mul"),s=E(t,"b","mul");[e,s]=ne(e,s);const r={a:e,b:s};return R.runKernel(Hr,r)}const D=P({mul_:Mb});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Rb(n){const t=E(n,"x","abs");if(t.dtype==="complex64"){const e={x:t};return R.runKernel(Bi,e)}else{const e={x:t};return R.runKernel(Ni,e)}}const fe=P({abs_:Rb});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function zb(n,t=null,e=!1){const r={x:E(n,"x","all","bool")},o={axis:t,keepDims:e};return R.runKernel(Cc,r,o)}const Lb=P({all_:zb});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ob(n,t=null,e=!1){const r={x:E(n,"x","any","bool")},o={axis:t,keepDims:e};return R.runKernel(Ac,r,o)}const Zu=P({any_:Ob});/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function _b(n,t=0){const s={x:E(n,"x","argMax")},r={axis:t};return R.runKernel(Ci,s,r)}const bo=P({argMax_:_b});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function nl(n,t,e,s,r="NHWC",o){const i=n[3],a=[...t,i],l=ko(r);return pn(n,a,e,o,s,null,null,l)}function Zs(n,t,e,s,r,o,i="channelsLast"){const[a,l]=Js(t);let c;if(i==="channelsLast")c=[a,l,n[3],n[3]];else if(i==="channelsFirst")c=[a,l,n[1],n[1]];else throw new Error(`Unknown dataFormat ${i}`);return pn(n,c,e,s,r,o,!1,i)}function yo(n,t,e,s,r,o,i="NDHWC"){const[a,l,c]=sl(t);let u,h;if(i==="NDHWC")h="channelsLast",u=[a,l,c,n[4],n[4]];else if(i==="NCDHW")h="channelsFirst",u=[a,l,c,n[1],n[1]];else throw new Error(`Unknown dataFormat ${i}`);return wo(n,u,e,s,r,!1,h,o)}function pn(n,t,e,s,r,o,i=!1,a="channelsLast"){let[l,c,u,h]=[-1,-1,-1,-1];if(a==="channelsLast")[l,c,u,h]=n;else if(a==="channelsFirst")[l,h,c,u]=n;else throw new Error(`Unknown dataFormat ${a}`);const[d,f,,p]=t,[g,m]=Js(e),[b,y]=Js(s),k=ws(d,b),w=ws(f,y),{padInfo:I,outHeight:S,outWidth:T}=Wb(r,c,u,g,m,k,w,o,a),C=i?p*h:p;let N;return a==="channelsFirst"?N=[l,C,S,T]:a==="channelsLast"&&(N=[l,S,T,C]),{batchSize:l,dataFormat:a,inHeight:c,inWidth:u,inChannels:h,outHeight:S,outWidth:T,outChannels:C,padInfo:I,strideHeight:g,strideWidth:m,filterHeight:d,filterWidth:f,effectiveFilterHeight:k,effectiveFilterWidth:w,dilationHeight:b,dilationWidth:y,inShape:n,outShape:N,filterShape:t}}function wo(n,t,e,s,r,o=!1,i="channelsLast",a){let[l,c,u,h,d]=[-1,-1,-1,-1,-1];if(i==="channelsLast")[l,c,u,h,d]=n;else if(i==="channelsFirst")[l,d,c,u,h]=n;else throw new Error(`Unknown dataFormat ${i}`);const[f,p,g,,m]=t,[b,y,k]=sl(e),[w,I,S]=sl(s),T=ws(f,w),C=ws(p,I),N=ws(g,S),{padInfo:$,outDepth:x,outHeight:F,outWidth:M}=Vb(r,c,u,h,b,y,k,T,C,N,a),O=o?m*d:m;let L;return i==="channelsFirst"?L=[l,O,x,F,M]:i==="channelsLast"&&(L=[l,x,F,M,O]),{batchSize:l,dataFormat:i,inDepth:c,inHeight:u,inWidth:h,inChannels:d,outDepth:x,outHeight:F,outWidth:M,outChannels:O,padInfo:$,strideDepth:b,strideHeight:y,strideWidth:k,filterDepth:f,filterHeight:p,filterWidth:g,effectiveFilterDepth:T,effectiveFilterHeight:C,effectiveFilterWidth:N,dilationDepth:w,dilationHeight:I,dilationWidth:S,inShape:n,outShape:L,filterShape:t}}function Bb(n,t,e,s,r){s==null&&(s=Ju(n,t,e));const o=n[0],i=n[1],a=Ys((o-t+2*s)/e+1,r),l=Ys((i-t+2*s)/e+1,r);return[a,l]}function Pb(n,t,e,s,r,o){r==null&&(r=Ju(n,t[0],s[0]));const i=[0,0,0,e];for(let a=0;a<3;a++)n[a]+2*r>=t[a]&&(i[a]=Ys((n[a]-t[a]+2*r)/s[a]+1,o));return i}function Ju(n,t,e,s=1){const r=ws(t,s);return Math.floor((n[0]*(e-1)-e+r)/2)}function Js(n){return typeof n=="number"?[n,n,n]:n.length===2?[n[0],n[1],1]:n}function sl(n){return typeof n=="number"?[n,n,n]:n}function ws(n,t){return t<=1?n:n+(n-1)*(t-1)}function Wb(n,t,e,s,r,o,i,a,l){let c,u,h;if(typeof n=="number"){c={top:n,bottom:n,left:n,right:n,type:n===0?"VALID":"NUMBER"};const f=Bb([t,e],o,s,n,a);u=f[0],h=f[1]}else if(n==="same"){u=Math.ceil(t/s),h=Math.ceil(e/r);const d=Math.max(0,(u-1)*s+o-t),f=Math.max(0,(h-1)*r+i-e),p=Math.floor(d/2),g=d-p,m=Math.floor(f/2),b=f-m;c={top:p,bottom:g,left:m,right:b,type:"SAME"}}else if(n==="valid")c={top:0,bottom:0,left:0,right:0,type:"VALID"},u=Math.ceil((t-o+1)/s),h=Math.ceil((e-i+1)/r);else if(typeof n=="object"){const d=l==="channelsLast"?n[1][0]:n[2][0],f=l==="channelsLast"?n[1][1]:n[2][1],p=l==="channelsLast"?n[2][0]:n[3][0],g=l==="channelsLast"?n[2][1]:n[3][1];c={top:d,bottom:f,left:p,right:g,type:d===0&&f===0&&p===0&&g===0?"VALID":"EXPLICIT"},u=Ys((t-o+d+f)/s+1,a),h=Ys((e-i+p+g)/r+1,a)}else throw Error(`Unknown padding parameter: ${n}`);return{padInfo:c,outHeight:u,outWidth:h}}function Vb(n,t,e,s,r,o,i,a,l,c,u){let h,d,f,p;if(n==="valid"&&(n=0),typeof n=="number"){h={top:n,bottom:n,left:n,right:n,front:n,back:n,type:n===0?"VALID":"NUMBER"};const m=Pb([t,e,s,1],[a,l,c],1,[r,o,i],n,u);d=m[0],f=m[1],p=m[2]}else if(n==="same"){d=Math.ceil(t/r),f=Math.ceil(e/o),p=Math.ceil(s/i);const g=(d-1)*r+a-t,m=(f-1)*o+l-e,b=(p-1)*i+c-s,y=Math.floor(g/2),k=g-y,w=Math.floor(m/2),I=m-w,S=Math.floor(b/2),T=b-S;h={top:w,bottom:I,left:S,right:T,front:y,back:k,type:"SAME"}}else throw Error(`Unknown padding parameter: ${n}`);return{padInfo:h,outDepth:d,outHeight:f,outWidth:p}}function Ys(n,t){if(!t)return Math.trunc(n);switch(t){case"round":return Math.round(n);case"ceil":return Math.ceil(n);case"floor":return Math.floor(n);default:throw new Error(`Unknown roundingMode ${t}`)}}function ks(n){const[t,e,s]=Js(n);return t===1&&e===1&&s===1}function Ze(n,t){return ks(n)||ks(t)}function xs(n){return Js(n).every(t=>t>0)}function ko(n){if(n==="NHWC")return"channelsLast";if(n==="NCHW")return"channelsFirst";throw new Error(`Unknown dataFormat ${n}`)}function be(n,t,e){if(e!=null){if(typeof t=="string")throw Error(`Error in ${n}: pad must be an integer when using dimRoundingMode ${e} but got pad ${t}.`);if(typeof t=="number")v($r(t),()=>`Error in ${n}: pad must be an integer when using dimRoundingMode ${e} but got pad ${t}.`);else if(typeof t=="object")t.forEach(s=>{s.forEach(r=>{v($r(r),()=>`Error in ${n}: pad must be an integer when using dimRoundingMode ${e} but got pad ${r}.`)})});else throw Error(`Error in ${n}: Unknown padding parameter: ${t}`)}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Gb(n,t){const s={x:E(n,"x","reshape","string_or_numeric")},r={shape:t};return R.runKernel(Ia,s,r)}const _=P({reshape_:Gb});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ub(n,t,e,s,r){const o=E(n,"x","avgPool","float32"),i=1;v(Ze(e,i),()=>`Error in avgPool: Either strides or dilations must be 1. Got strides ${e} and dilations '${i}'`);let a=o,l=!1;o.rank===3&&(l=!0,a=_(o,[1,o.shape[0],o.shape[1],o.shape[2]])),v(a.rank===4,()=>`Error in avgPool: x must be rank 4 but got rank ${a.rank}.`),be("avgPool",s,r);const c={x:a},u={filterSize:t,strides:e,pad:s,dimRoundingMode:r};let h=R.runKernel(Ri,c,u);return h=Q(h,o.dtype),l?_(h,[h.shape[1],h.shape[2],h.shape[3]]):h}const Hb=P({avgPool_:Ub});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function qb(n,t,e,s,r,o="NDHWC"){const i=E(n,"x","avgPool3d","float32");let a=i,l=!1;i.rank===4&&(l=!0,a=_(i,[1,i.shape[0],i.shape[1],i.shape[2],i.shape[3]])),v(a.rank===5,()=>`Error in avgPool3d: x must be rank 5 but got rank ${a.rank}.`),v(o==="NDHWC",()=>`Error in avgPool3d: Only NDHWC is currently supported, but got dataFormat of ${o}`),v(typeof e=="number"&&e>0||Array.isArray(e)&&e[0]>0&&e[1]>0&&e[2]>0,()=>`Error in avgPool3d: Stride must be > 0, but got '${e}'`),be("avgPool3d",s,r);const c={x:a},u={filterSize:t,strides:e,pad:s,dimRoundingMode:r,dataFormat:o};let h=R.runKernel(zi,c,u);return h=Q(h,a.dtype),l?_(h,[h.shape[1],h.shape[2],h.shape[3],h.shape[4]]):h}const jb=P({avgPool3d_:qb});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Kb(n,t=0){v(n.length>=1,()=>"Pass at least one tensor to concat");const e=Ou(n,"tensors","concat","string_or_numeric");if(e[0].dtype==="complex64"&&e.forEach(o=>{if(o.dtype!=="complex64")throw new Error(`Cannot concatenate complex64 tensors with a tensor
          with dtype ${o.dtype}. `)}),e.length===1)return Qn(e[0]);const s=e,r={axis:t};return R.runKernel(Pi,s,r)}const _e=P({concat_:Kb});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Xb(n,t,e=!1,s=!1){let r=E(n,"a","matMul"),o=E(t,"b","matMul");[r,o]=ne(r,o);const i={a:r,b:o},a={transposeA:e,transposeB:s};return R.runKernel(Li,i,a)}const Tt=P({matMul_:Xb});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Zb(n){const e={x:E(n,"x","sigmoid","float32")};return R.runKernel(to,e)}const xo=P({sigmoid_:Zb});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Jb(n,t,e){const s=E(n,"x","slice","string_or_numeric");if(s.rank===0)throw new Error("Slicing scalar is not possible");const r={x:s},o={begin:t,size:e};return R.runKernel(Ta,r,o)}const Bt=P({slice_:Jb});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Yb(n){const e={x:E(n,"x","tanh","float32")};return R.runKernel(ro,e)}const rl=P({tanh_:Yb});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Qb(n,t,e){const s=E(n,"x","batchToSpaceND"),r=t.reduce((a,l)=>a*l);v(s.rank>=1+t.length,()=>`input rank is ${s.rank} but should be > than blockShape.length ${t.length}`),v(e.length===t.length,()=>`crops.length is ${e.length} but should be equal to blockShape.length  ${t.length}`),v(s.shape[0]%r===0,()=>`input tensor batch is ${s.shape[0]} but is not divisible by the product of the elements of blockShape ${t.join(" * ")} === ${r}`);const o={x:s},i={blockShape:t,crops:e};return R.runKernel(Oi,o,i)}const ty=P({batchToSpaceND_:Qb});function ey(n){let t;return n.rank===0||n.rank===1?t=_(n,[1,1,1,n.size]):n.rank===2?t=_(n,[1,1,n.shape[0],n.shape[1]]):n.rank===3?t=_(n,[1,n.shape[0],n.shape[1],n.shape[2]]):t=n,t}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function ny(n,t,e,s,r,o){o==null&&(o=.001);const i=E(n,"x","batchNorm"),a=E(t,"mean","batchNorm"),l=E(e,"variance","batchNorm");let c;r!=null&&(c=E(r,"scale","batchNorm"));let u;s!=null&&(u=E(s,"offset","batchNorm")),v(a.rank===l.rank,()=>"Batch normalization gradient requires mean and variance to have equal ranks."),v(u==null||a.rank===u.rank,()=>"Batch normalization gradient requires mean and offset to have equal ranks."),v(c==null||a.rank===c.rank,()=>"Batch normalization gradient requires mean and scale to have equal ranks.");const d={x:ey(i),scale:c,offset:u,mean:a,variance:l},f={varianceEpsilon:o},p=R.runKernel(Ji,d,f);return _(p,i.shape)}const ol=P({batchNorm_:ny});function sy(n,t,e,s,r,o){const i=E(n,"x","batchNorm"),a=E(t,"mean","batchNorm"),l=E(e,"variance","batchNorm");let c;r!=null&&(c=E(r,"scale","batchNorm"));let u;return s!=null&&(u=E(s,"offset","batchNorm")),v(i.rank===2,()=>`Error in batchNorm2D: x must be rank 2 but got rank ${i.rank}.`),v(a.rank===2||a.rank===1,()=>`Error in batchNorm2D: mean must be rank 2 or rank 1 but got rank ${a.rank}.`),v(l.rank===2||l.rank===1,()=>`Error in batchNorm2D: variance must be rank 2 or rank 1 but got rank ${l.rank}.`),c!=null&&v(c.rank===2||c.rank===1,()=>`Error in batchNorm2D: scale must be rank 2 or rank 1 but got rank ${c.rank}.`),u!=null&&v(u.rank===2||u.rank===1,()=>`Error in batchNorm2D: offset must be rank 2 or rank 1 but got rank ${u.rank}.`),ol(i,a,l,u,c,o)}const ry=P({batchNorm2d_:sy});function oy(n,t,e,s,r,o){const i=E(n,"x","batchNorm"),a=E(t,"mean","batchNorm"),l=E(e,"variance","batchNorm");let c;r!=null&&(c=E(r,"scale","batchNorm"));let u;return s!=null&&(u=E(s,"offset","batchNorm")),v(i.rank===3,()=>`Error in batchNorm3D: x must be rank 3 but got rank ${i.rank}.`),v(a.rank===3||a.rank===1,()=>`Error in batchNorm3D: mean must be rank 3 or rank 1 but got rank ${a.rank}.`),v(l.rank===3||l.rank===1,()=>`Error in batchNorm3D: variance must be rank 3 or rank 1 but got rank ${l.rank}.`),c!=null&&v(c.rank===3||c.rank===1,()=>`Error in batchNorm3D: scale must be rank 3 or rank 1 but got rank ${c.rank}.`),u!=null&&v(u.rank===3||u.rank===1,()=>`Error in batchNorm3D: offset must be rank 3 or rank 1 but got rank ${u.rank}.`),ol(i,a,l,u,c,o)}const iy=P({batchNorm3d_:oy});function ay(n,t,e,s,r,o){const i=E(n,"x","batchNorm"),a=E(t,"mean","batchNorm"),l=E(e,"variance","batchNorm");let c;r!=null&&(c=E(r,"scale","batchNorm"));let u;return s!=null&&(u=E(s,"offset","batchNorm")),v(i.rank===4,()=>`Error in batchNorm4D: x must be rank 4 but got rank ${i.rank}.`),v(a.rank===4||a.rank===1,()=>`Error in batchNorm4D: mean must be rank 4 or rank 1 but got rank ${a.rank}.`),v(l.rank===4||l.rank===1,()=>`Error in batchNorm4D: variance must be rank 4 or rank 1 but got rank ${l.rank}.`),c!=null&&v(c.rank===4||c.rank===1,()=>`Error in batchNorm4D: scale must be rank 4 or rank 1 but got rank ${c.rank}.`),u!=null&&v(u.rank===4||u.rank===1,()=>`Error in batchNorm4D: offset must be rank 4 or rank 1 but got rank ${u.rank}.`),ol(i,a,l,u,c,o)}const ly=P({batchNorm4d_:ay});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function cy(n,t,e){const s=E(n,"x","bincount"),r=E(t,"weights","bincount");v(s.dtype==="int32",()=>`Error in bincount: input dtype must be int32, but got ${s.dtype}`),v(e>=0,()=>`size must be non-negative, but got ${e}.`),v(r.size===s.size||r.size===0,()=>`Error in bincount: weights must have the same size as input or0-length, but got input shape: ${s.shape}, weights shape: ${r.shape}.`);const o={x:s,weights:r},i={size:e};return R.runKernel(Mc,o,i)}const uy=P({bincount_:cy});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function hy(n,t){let e=E(n,"broadcastTo","x");const s=e.shape;if(dn(t),t.length<e.rank)throw new Error(`broadcastTo(): shape.length=${t.length} < input.rank=${e.rank}.`);if(t.length>e.rank){const c=e.shape.slice();for(;c.length<t.length;)c.unshift(1);e=_(e,c)}const r=e.shape,o=Array.from(t);for(let c=t.length-1;c>=0;c--)if(r[c]===t[c])o[c]=1;else if(e.shape[c]!==1)throw new Error(`broadcastTo(): [${s}] cannot be broadcast to [${t}].`);if(o.map((c,u)=>c>1?u:-1).filter(c=>c>=0).length===0)return Qn(e);const a={x:e},l={reps:o};return R.runKernel(oo,a,l)}const Io=P({broadcastTo_:hy});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function So(n,t,e){dn(n),e=e||Ws(t);const s={shape:n,value:t,dtype:e};return R.runKernel(jc,{},s)}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function dy(n,t,e){const s=E(n,"x","clipByValue");if(v(t<=e,()=>`Error in clip: min (${t}) must be less than or equal to max (${e}).`),t===e)return So(s.shape,t,s.dtype);const r={x:s},o={clipValueMin:t,clipValueMax:e};return R.runKernel(Er,r,o)}const $e=P({clipByValue_:dy});function fy(n){return _e(n,0)}const py=P({concat1d_:fy});function my(n,t){return _e(n,t)}const gy=P({concat2d_:my});function by(n,t){return _e(n,t)}const yy=P({concat3d_:by});function wy(n,t){return _e(n,t)}const ky=P({concat4d_:wy});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function xy(n,t,e,s,r="NHWC",o=[1,1],i){const a=E(n,"x","conv2d","float32"),l=E(t,"filter","conv2d","float32");let c=a,u=!1;a.rank===3&&(u=!0,c=_(a,[1,a.shape[0],a.shape[1],a.shape[2]])),v(c.rank===4,()=>`Error in conv2d: input must be rank 4, but got rank ${c.rank}.`),v(l.rank===4,()=>`Error in conv2d: filter must be rank 4, but got rank ${l.rank}.`),be("conv2d",s,i);const h=r==="NHWC"?c.shape[3]:c.shape[1];v(h===l.shape[2],()=>`Error in conv2d: depth of input (${h}) must match input depth for filter ${l.shape[2]}.`),v(Ze(e,o),()=>`Error in conv2D: Either strides or dilations must be 1. Got strides ${e} and dilations '${o}'`),v(xs(o),()=>"Error in conv2D: Dilated rates should be larger than 0."),v(xs(e),()=>"Error in conv2D: Strides should be larger than 0.");const d={x:c,filter:l},f={strides:e,pad:s,dataFormat:r,dilations:o,dimRoundingMode:i},p=R.runKernel(Wi,d,f);return u?_(p,[p.shape[1],p.shape[2],p.shape[3]]):p}const Is=P({conv2d_:xy});function Iy(n,t,e,s,r="NWC",o=1,i){const a=E(n,"x","conv1d"),l=E(t,"filter","conv1d");let c=a,u=!1;a.rank===2&&(u=!0,c=_(a,[1,a.shape[0],a.shape[1]])),v(c.rank===3,()=>`Error in conv1d: input must be rank 3, but got rank ${c.rank}.`),v(l.rank===3,()=>`Error in conv1d: filter must be rank 3, but got rank ${l.rank}.`),be("conv1d",s,i),v(c.shape[2]===l.shape[1],()=>`Error in conv1d: depth of input (${c.shape[2]}) must match input depth for filter ${l.shape[1]}.`),v(Ze(e,o),()=>`Error in conv1D: Either stride or dilation must be 1. Got stride ${e} and dilation '${o}'`),v(xs(o),()=>"Error in conv1D: Dilated rates should be larger than 0."),v(xs(e),()=>"Error in conv1D: Stride should be larger than 0."),v(r==="NWC",()=>`Error in conv1d: got dataFormat of ${r} but only NWC is currently supported.`);const h=_(l,[1,l.shape[0],l.shape[1],l.shape[2]]),d=_(c,[c.shape[0],1,c.shape[1],c.shape[2]]),m=Is(d,h,[1,e],s,"NHWC",[1,o],i);return u?_(m,[m.shape[2],m.shape[3]]):_(m,[m.shape[0],m.shape[2],m.shape[3]])}const Sy=P({conv1d_:Iy});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function vy(n,t,e,s,r,o="NHWC",i){v(n.length===t.rank,()=>`Length of inShape (${n.length}) and rank of dy (${t.rank}) must match`);let a=n,l=t,c=!1;t.rank===3&&(c=!0,l=_(t,[1,t.shape[0],t.shape[1],t.shape[2]]),a=[1,n[0],n[1],n[2]]),v(a.length===4,()=>`Error in conv2dDerInput: inShape must be length 4, but got length ${a.length}.`),v(l.rank===4,()=>`Error in conv2dDerInput: dy must be rank 4, but got rank ${l.rank}`),v(e.rank===4,()=>`Error in conv2dDerInput: filter must be rank 4, but got rank ${e.rank}`);const u=o==="NHWC"?a[3]:a[1],h=o==="NHWC"?l.shape[3]:l.shape[1];v(u===e.shape[2],()=>`Error in conv2dDerInput: depth of input (${u}) must match input depth for filter ${e.shape[2]}.`),v(h===e.shape[3],()=>`Error in conv2dDerInput: depth of output (${h}) must match output depth for filter ${e.shape[3]}.`),be("conv2dDerInput",r,i);const d={dy:l,filter:e},f={strides:s,pad:r,dataFormat:o,dimRoundingMode:i,inputShape:a},p=R.runKernel(Vi,d,f);return c?_(p,[p.shape[1],p.shape[2],p.shape[3]]):p}const il=P({conv2DBackpropInput_:vy});function Ny(n,t,e,s,r,o){const i=E(n,"x","conv2dTranspose"),a=E(t,"filter","conv2dTranspose");return il(e,i,a,s,r,"NHWC",o)}const $y=P({conv2dTranspose_:Ny});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ty(n,t,e,s,r="NDHWC",o=[1,1,1]){const i=E(n,"x","conv3d"),a=E(t,"filter","conv3d");let l=i,c=!1;i.rank===4&&(c=!0,l=_(i,[1,i.shape[0],i.shape[1],i.shape[2],i.shape[3]])),v(l.rank===5,()=>`Error in conv3d: input must be rank 5, but got rank ${l.rank}.`),v(a.rank===5,()=>`Error in conv3d: filter must be rank 5, but got rank ${a.rank}.`),v(l.shape[4]===a.shape[3],()=>`Error in conv3d: depth of input (${l.shape[4]}) must match input depth for filter ${a.shape[3]}.`),v(Ze(e,o),()=>`Error in conv3D: Either strides or dilations must be 1. Got strides ${e} and dilations '${o}'`),v(r==="NDHWC",()=>`Error in conv3d: got dataFormat of ${r} but only NDHWC is currently supported.`),v(xs(o),()=>"Error in conv3D: Dilated rates should be larger than 0."),v(xs(e),()=>"Error in conv3D: Strides should be larger than 0.");const u={x:l,filter:a},h={strides:e,pad:s,dataFormat:r,dilations:o},d=R.runKernel(Gi,u,h);return c?_(d,[d.shape[1],d.shape[2],d.shape[3],d.shape[4]]):d}const Cy=P({conv3d_:Ty});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ay(n,t,e,s,r){v(n.length===t.rank,()=>`Length of inShape (${n.length}) and rank of dy (${t.rank}) must match`);let o=n,i=t,a=!1;t.rank===4&&(a=!0,i=_(t,[1,t.shape[0],t.shape[1],t.shape[2],t.shape[3]]),o=[1,n[0],n[1],n[2],n[3]]);const l=o[4],c=i.shape[4];v(o.length===5,()=>`Error in conv3dDerInput: inShape must be length 5, but got length ${o.length}.`),v(i.rank===5,()=>`Error in conv3dDerInput: dy must be rank 5, but got rank ${i.rank}`),v(e.rank===5,()=>`Error in conv3dDerInput: filter must be rank 5, but got rank ${e.rank}`),v(l===e.shape[3],()=>`Error in conv3dDerInput: depth of input (${l}) must match input depth for filter ${e.shape[3]}.`),v(c===e.shape[4],()=>`Error in conv3dDerInput: depth of output (${c}) must match output depth for filter ${e.shape[4]}.`);const u={dy:i,filter:e},h={pad:r,strides:s,inputShape:o},d=R.runKernel(_c,u,h);return a?_(d,[d.shape[1],d.shape[2],d.shape[3],d.shape[4]]):d}const Yu=P({conv3DBackpropInput_:Ay});function Ey(n,t,e,s,r){const o=E(n,"x","conv3dTranspose"),i=E(t,"filter","conv3dTranspose");return Yu(e,o,i,s,r)}const Dy=P({conv3dTranspose_:Ey});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Fy(n){const e={x:E(n,"x","cos","float32")};return R.runKernel(Dr,e)}const Qu=P({cos_:Fy});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function My(n){const e={x:E(n,"x","cosh","float32")};return R.runKernel(Fr,e)}const Ry=P({cosh_:My});/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the 'License');
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an 'AS IS' BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function zy(n,t=0,e=!1,s=!1){const o={x:E(n,"x","cumprod")},i={axis:t,exclusive:e,reverse:s};return R.runKernel(Bc,o,i)}const th=P({cumprod_:zy});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ly(n,t=0,e=!1,s=!1){const o={x:E(n,"x","cumsum")},i={axis:t,exclusive:e,reverse:s};return R.runKernel(Ui,o,i)}const Oy=P({cumsum_:Ly});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function _y(n,t,e,s=!1){const r=E(n,"x","denseBincount"),o=E(t,"weights","denseBincount");v(r.dtype==="int32",()=>`Error in denseBincount: input dtype must be int32, but got ${r.dtype}`),v(r.rank<=2,()=>`Error in denseBincount: input must be at most rank 2, but got rank ${r.rank}.`),v(e>=0,()=>`size must be non-negative, but got ${e}.`),v(o.size===r.size||o.size===0,()=>`Error in denseBincount: weights must have the same shape as x or 0-length, but got x shape: ${r.shape}, weights shape: ${o.shape}.`);const i={x:r,weights:o},a={size:e,binaryOutput:s};return R.runKernel(Wc,i,a)}const eh=P({denseBincount_:_y});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function By(n,t,e,s,r="NHWC",o=[1,1],i){const a=E(n,"x","depthwiseConv2d","float32"),l=E(t,"filter","depthwiseConv2d","float32");let c=a,u=!1;a.rank===3&&(u=!0,c=_(a,[1,a.shape[0],a.shape[1],a.shape[2]])),v(c.rank===4,()=>`Error in depthwiseConv2d: input must be rank 4, but got rank ${c.rank}.`),v(l.rank===4,()=>`Error in depthwiseConv2d: filter must be rank 4, but got rank ${l.rank}.`);const h=r==="NHWC"?c.shape[3]:c.shape[1];v(h===l.shape[2],()=>`Error in depthwiseConv2d: number of input channels (${h}) must match the inChannels dimension in filter ${l.shape[2]}.`),be("depthwiseConv2d",s,i);const d={x:c,filter:l},f={strides:e,pad:s,dataFormat:r,dilations:o,dimRoundingMode:i},p=R.runKernel(Hi,d,f);return u?_(p,[p.shape[1],p.shape[2],p.shape[3]]):p}const nh=P({depthwiseConv2d_:By});/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function vo(n,t){const e=n.length,s=[];for(let r=0;r<e;r++){const o=e-1-r,i=n[o]||1;(t[t.length-1-r]||1)>1&&i===1&&s.unshift(o)}return s}function Yt(n,t){const e=[];for(let s=0;s<t.length;s++){const r=n[n.length-s-1],o=t.length-s-1,i=t[o];(r==null||r===1&&i>1)&&e.unshift(o)}return e}function Ct(n,t){const e=Math.max(n.length,t.length),s=new Array(e);for(let r=0;r<e;r++){let o=n[n.length-r-1];o==null&&(o=1);let i=t[t.length-r-1];if(i==null&&(i=1),o===1)s[e-r-1]=i;else if(i===1)s[e-r-1]=o;else if(o!==i){const a=`Operands could not be broadcast together with shapes ${n} and ${t}.`;throw Error(a)}else s[e-r-1]=o}return s}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Py(n,t){let e=E(n,"a","equal","string_or_numeric"),s=E(t,"b","equal","string_or_numeric");[e,s]=ne(e,s),Ct(e.shape,s.shape);const r={a:e,b:s};return R.runKernel(Ki,r)}const Tn=P({equal_:Py});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Wy(n,t,e){const s=E(t,"a","where"),r=E(e,"b","where"),o=E(n,"condition","where","bool"),i=Ct(Ct(o.shape,s.shape),r.shape),a=Io(o,i),l=Io(s,i),c=Io(r,i),u={condition:a,t:l,e:c};return R.runKernel($a,u)}const ye=P({where_:Wy});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Vy(n){const e={x:E(n,"x","zerosLike")};return R.runKernel(Oa,e)}const wt=P({zerosLike_:Vy});/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Gy(n,...t){const e=t.map((r,o)=>E(r,`tensors${o}`,"einsum")),s={equation:n};return R.runKernel(Hc,e,s)}const Qs=P({einsum_:Gy});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Uy(n){const e={x:E(n,"x","elu","float32")};return R.runKernel(Rr,e)}const al=P({elu_:Uy});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Hy(n){let t=E(n,"x","erf");v(t.dtype==="int32"||t.dtype==="float32",()=>"Input dtype must be `int32` or `float32`."),t.dtype==="int32"&&(t=Q(t,"float32"));const e={x:t};return R.runKernel(zr,e)}const qy=P({erf_:Hy});/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function sh(n,t){for(let e=0;e<n.length;++e)if(n[n.length-e-1]!==t-1-e)return!1;return!0}function jy(n,t,e){const s=n.length+t.length,r=[];let o=0,i=0;for(let a=0;a<s;a++)e.indexOf(a)===-1?r.push(n[o++]):r.push(t[i++]);return r}function Je(n,t){const e=[],s=n.length;for(let o=0;o<s;o++)t.indexOf(o)===-1&&e.push(n[o]);const r=t.map(o=>n[o]);return[e,r]}function Te(n,t){const e=t.map(s=>1);return jy(n,e,t)}function ts(n,t,e){v(sh(t,e),()=>`${n} supports only inner-most axes for now. Got axes ${t} and rank-${e} input.`)}function Ce(n,t){if(sh(n,t))return null;const e=[];for(let s=0;s<t;++s)n.indexOf(s)===-1&&e.push(s);return n.forEach(s=>e.push(s)),e}function tr(n){return n.map((t,e)=>[e,t]).sort((t,e)=>t[1]-e[1]).map(t=>t[0])}function Ye(n,t){const e=[];for(let s=t-n;s<t;++s)e.push(s);return e}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ky(n,t=null,e=!1){const r={x:E(n,"x","max")},o={reductionIndices:t,keepDims:e};return R.runKernel(la,r,o)}const Qe=P({max_:Ky});/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Xy(n,t=null,e=!1){const r={x:E(n,"x","min")},o={axis:t,keepDims:e};return R.runKernel(da,r,o)}const ll=P({min_:Xy});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Zy(n,t){let e=E(n,"base","pow"),s=E(t,"exp","pow");[e,s]=ne(e,s);const r={a:e,b:s};return R.runKernel(qr,r)}const Ss=P({pow_:Zy});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function kt(n,t){if((Ne(n)&&t!=="string"||Array.isArray(n))&&t!=="complex64")throw new Error("Error creating a new Scalar: value must be a primitive (number|boolean|string)");if(t==="string"&&Ne(n)&&!(n instanceof Uint8Array))throw new Error("When making a scalar from encoded string, the value must be `Uint8Array`.");return mo(n,[],[],t)}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Jy(n){const e={x:E(n,"x","sqrt","float32")};return R.runKernel(no,e)}const ue=P({sqrt_:Jy});/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Yy(n){const t=E(n,"x","square"),e={};return R.runKernel("Square",{x:t},e)}const Mt=P({square_:Yy});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Qy(n,t=null,e=!1){let s=E(n,"x","sum");s.dtype==="bool"&&(s=Q(s,"int32"));const r={x:s},o={axis:t,keepDims:e};return R.runKernel(Aa,r,o)}const st=P({sum_:Qy});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function t0(n,t="euclidean",e=null,s=!1){n=E(n,"x","norm");const r=rh(n,t,e);let o=r.shape;if(s){const i=Ft(e,n.shape);o=Te(r.shape,i)}return _(r,o)}function rh(n,t,e=null){if(n.rank===0)return fe(n);if(n.rank!==1&&e===null)return rh(_(n,[-1]),t,e);if(n.rank===1||typeof e=="number"||Array.isArray(e)&&e.length===1){if(t===1)return st(fe(n),e);if(t===1/0)return Qe(fe(n),e);if(t===-1/0)return ll(fe(n),e);if(t==="euclidean"||t===2)return ue(st(Ss(fe(n),kt(2,"int32")),e));throw new Error(`Error in norm: invalid ord value: ${t}`)}if(Array.isArray(e)&&e.length===2){if(t===1)return Qe(st(fe(n),e[0]),e[1]-1);if(t===1/0)return Qe(st(fe(n),e[1]),e[0]);if(t===-1/0)return ll(st(fe(n),e[1]),e[0]);if(t==="fro"||t==="euclidean")return ue(st(Mt(n),e));throw new Error(`Error in norm: invalid ord value: ${t}`)}throw new Error(`Error in norm: invalid axis: ${e}`)}const oh=P({norm_:t0});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function e0(n){const e={x:E(n,"x","exp")};return R.runKernel(Lr,e)}const mn=P({exp_:e0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function n0(n,t=0){const e=E(n,"x","expandDims","string_or_numeric");v(t<=e.rank,()=>"Axis must be <= rank of the tensor");const s={input:e},r={dim:t};return R.runKernel(Xi,s,r)}const we=P({expandDims_:n0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function s0(n,t){const e=E(n,"x","tile","string_or_numeric");v(e.rank===t.length,()=>`Error in transpose: rank of input ${e.rank} must match length of reps ${t}.`);const s={x:e},r={reps:t};return R.runKernel(oo,s,r)}const tn=P({tile_:s0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function r0(n,t,e,s="float32"){t==null&&(t=n);const r=mt([n,t],s),o=n<=t?n:t;for(let a=0;a<o;++a)r.set(1,a,a);const i=_(r.toTensor(),[n,t]);if(e==null)return i;if(e.length===1)return tn(we(i,0),[e[0],1,1]);if(e.length===2)return tn(we(we(i,0),0),[e[0],e[1],1,1]);if(e.length===3)return tn(we(we(we(i,0),0),0),[e[0],e[1],e[2],1,1]);throw new Error(`eye() currently supports only 1D and 2D batchShapes, but received ${e.length}D.`)}const ih=P({eye_:r0});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function o0(n){const e={x:E(n,"x","floor","float32")};return R.runKernel(Or,e)}const cl=P({floor_:o0});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function i0(n,t,e=0,s=0){const r=E(n,"x","gather"),o=E(t,"indices","gather","int32"),i={x:r,indices:o},a={axis:e,batchDims:s};return R.runKernel(Yi,i,a)}const ah=P({gather_:i0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function a0(n,t){let e=E(n,"a","greater","string_or_numeric"),s=E(t,"b","greater","string_or_numeric");[e,s]=ne(e,s),Ct(e.shape,s.shape);const r={a:e,b:s};return R.runKernel(Qi,r)}const Ae=P({greater_:a0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function l0(n,t){let e=E(n,"a","greaterEqual","string_or_numeric"),s=E(t,"b","greaterEqual","string_or_numeric");[e,s]=ne(e,s),Ct(e.shape,s.shape);const r={a:e,b:s};return R.runKernel(Br,r)}const vs=P({greaterEqual_:l0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function c0(n){const e={input:E(n,"input","imag")};return R.runKernel(Xc,e)}const u0=P({imag_:c0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function h0(n,t=.2){const s={x:E(n,"x","leakyRelu")},r={alpha:t};return R.runKernel(sa,s,r)}const lh=P({leakyRelu_:h0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function d0(n,t){let e=E(n,"a","less","string_or_numeric"),s=E(t,"b","less","string_or_numeric");[e,s]=ne(e,s),Ct(e.shape,s.shape);const r={a:e,b:s};return R.runKernel(ra,r)}const ul=P({less_:d0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function f0(n,t){let e=E(n,"a","lessEqual","string_or_numeric"),s=E(t,"b","lessEqual","string_or_numeric");[e,s]=ne(e,s),Ct(e.shape,s.shape);const r={a:e,b:s};return R.runKernel(oa,r)}const er=P({lessEqual_:f0});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function p0(n){const e={x:E(n,"x","log","float32")};return R.runKernel(Wr,e)}const gn=P({log_:p0});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function m0(n){const e={x:E(n,"x","log1p")};return R.runKernel(Vr,e)}const g0=P({log1p_:m0});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function b0(n,t){v(ki(n),()=>"The f passed in variableGrads(f) must be a function"),v(t==null||Array.isArray(t)&&t.every(c=>c instanceof ho),()=>"The varList passed in variableGrads(f, varList) must be an array of variables");const e=t!=null;if(!e){t=[];for(const c in R.registeredVariables)t.push(R.registeredVariables[c])}const s=e?t.filter(c=>!c.trainable):null,r=t.length;t=t.filter(c=>c.trainable),v(t.length>0,()=>`variableGrads() expects at least one of the input variables to be trainable, but none of the ${r} variables is trainable.`);const o=!0,{value:i,grads:a}=R.gradients(n,t,null,o);v(a.some(c=>c!=null),()=>"Cannot find a connection between any variable and the result of the loss function y=f(x). Please make sure the operations that use variables are inside the function f passed to minimize()."),v(i.rank===0,()=>`The f passed in variableGrads(f) must return a scalar, but it returned a rank-${i.rank} tensor`);const l={};return t.forEach((c,u)=>{a[u]!=null&&(l[c.name]=a[u])}),s!=null&&s.forEach(c=>l[c.name]=null),{value:i,grads:l}}function nr(n){return R.customGrad(n)}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function y0(n){const e={x:E(n,"x","neg")};return R.runKernel(pa,e)}const se=P({neg_:y0});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function w0(n){const e={x:E(n,"x","softplus")};return R.runKernel(eo,e)}const hl=P({softplus_:w0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function k0(n,t){let e=E(n,"a","sub"),s=E(t,"b","sub");[e,s]=ne(e,s);const r={a:e,b:s};return R.runKernel(so,r)}const lt=P({sub_:k0});/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function x0(n,t=-1){const e=E(n,"logits","logSoftmax");if(t===-1&&(t=e.rank-1),t!==e.rank-1)throw Error(`Log Softmax along a non-last dimension is not yet supported. Logits was rank ${e.rank} and axis was ${t}`);return nr((r,o)=>{const a=Qe(r,t,!0),l=lt(r,a),c=lt(Q(l,"float32"),gn(st(mn(l),t,!0)));return o([c]),{value:c,gradFunc:(h,d)=>{const[f]=d,p=!0,g=mn(f);return lt(h,D(st(h,t,p),g))}}})(e)}const I0=P({logSoftmax_:x0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function S0(n,t=null,e=!1){const s=E(n,"x","logSumExp"),r=Ft(t,s.shape),o=Qe(s,r,!0),i=lt(s,o),a=mn(i),l=st(a,r),c=gn(l),u=X(_(o,c.shape),c);if(e){const h=Te(u.shape,r);return _(u,h)}return u}const v0=P({logSumExp_:S0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function N0(n,t){const e=E(n,"a","logicalAnd","bool"),s=E(t,"b","logicalAnd","bool");Ct(e.shape,s.shape);const r={a:e,b:s};return R.runKernel(ia,r)}const Ns=P({logicalAnd_:N0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function $0(n){const e={x:E(n,"x","logicalNot","bool")};return R.runKernel(aa,e)}const T0=P({logicalNot_:$0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function C0(n,t,e,s,r){const o=E(n,"x","maxPool"),i=1;let a=o,l=!1;o.rank===3&&(l=!0,a=_(o,[1,o.shape[0],o.shape[1],o.shape[2]])),v(a.rank===4,()=>`Error in maxPool: input must be rank 4 but got rank ${a.rank}.`),v(Ze(e,i),()=>`Error in maxPool: Either strides or dilations must be 1. Got strides ${e} and dilations '${i}'`),be("maxPool",s,r);const c={x:a},u={filterSize:t,strides:e,pad:s,dimRoundingMode:r},h=R.runKernel(ca,c,u);return l?_(h,[h.shape[1],h.shape[2],h.shape[3]]):h}const A0=P({maxPool_:C0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function E0(n,t=[1,1,1],e,s,r,o="NDHWC"){const i=E(n,"x","maxPool3d");let a=i,l=!1;i.rank===4&&(l=!0,a=_(i,[1,i.shape[0],i.shape[1],i.shape[2],i.shape[3]])),v(a.rank===5,()=>`Error in maxPool3d: x must be rank 5 but got rank ${a.rank}.`),v(o==="NDHWC",()=>`Error in maxPool3d: Only NDHWC is currently supported, but got dataFormat of ${o}`),be("maxPool3d",s,r);const c={x:a},u={filterSize:t,strides:e,pad:s,dimRoundingMode:r,dataFormat:o},h=R.runKernel(ua,c,u);return l?_(h,[h.shape[1],h.shape[2],h.shape[3],h.shape[4]]):h}const D0=P({maxPool3d_:E0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function F0(n,t){let e=E(n,"a","maximum"),s=E(t,"b","maximum");[e,s]=ne(e,s),e.dtype==="bool"&&(e=Q(e,"int32"),s=Q(s,"int32")),Ct(e.shape,s.shape);const r={a:e,b:s};return R.runKernel(Gr,r)}const es=P({maximum_:F0});/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function M0(n,t=null,e=!1){const r={x:E(n,"x","mean")},o={axis:t,keepDims:e};return R.runKernel(ha,r,o)}const Ut=P({mean_:M0});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function ae(n,t="float32"){if(dn(n),t==="complex64"){const s=ae(n,"float32"),r=ae(n,"float32");return po(s,r)}const e=ie(Z(n),t);return R.makeTensor(e,n,t)}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Cn(n,t="float32"){if(dn(n),t==="complex64"){const s=Cn(n,"float32"),r=ae(n,"float32");return po(s,r)}const e=xi(Z(n),t);return R.makeTensor(e,n,t)}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function R0(n,t){let e=E(n,"a","minimum"),s=E(t,"b","minimum");[e,s]=ne(e,s),e.dtype==="bool"&&(e=Q(e,"int32"),s=Q(s,"int32")),Ct(e.shape,s.shape);const r={a:e,b:s};return R.runKernel(Ur,r)}const No=P({minimum_:R0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function z0(n,t=null,e=!1){n=E(n,"x","moments");const s=Ft(t,n.shape),r=Ut(n,s,e);let o=r.shape;e||(o=Te(r.shape,s));const i=Mt(lt(Q(n,"float32"),_(r,o))),a=Ut(i,s,e);return{mean:r,variance:a}}const dl=P({moments_:z0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function L0(n,t){let e=E(n,"a","notEqual","string_or_numeric"),s=E(t,"b","notEqual","string_or_numeric");[e,s]=ne(e,s),Ct(e.shape,s.shape);const r={a:e,b:s};return R.runKernel(ma,r)}const fl=P({notEqual_:L0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function O0(n,t,e=1,s=0,r="int32"){if(t<2)throw new Error(`Error in oneHot: depth must be >=2, but it is ${t}`);const i={indices:E(n,"indices","oneHot","int32")},a={dtype:r,depth:t,onValue:e,offValue:s};return R.runKernel(ba,i,a)}const _0=P({oneHot_:O0});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function B0(n){const e={x:E(n,"x","onesLike")};return R.runKernel(ga,e)}const Be=P({onesLike_:B0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function P0(n,t,e=0){const s=E(n,"x","pad");if(s.rank===0)throw new Error("pad(scalar) is not defined. Pass non-scalar to pad");const r={paddings:t,constantValue:e},o={x:s};return R.runKernel(wa,o,r)}const ch=P({pad_:P0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function W0(n,t,e){const s=E(n,"x","spaceToBatchND");v(s.rank>=1+t.length,()=>`input rank ${s.rank} should be > than [blockShape] ${t.length}`),v(e.length===t.length,()=>`paddings.shape[0] ${e.length} must be equal to [blockShape] ${t.length}`),v(s.shape.reduce((i,a,l)=>l>0&&l<=t.length?i&&(a+e[l-1][0]+e[l-1][1])%t[l-1]===0:i,!0),()=>`input spatial dimensions ${s.shape.slice(1)} with paddings ${e.toString()} must be divisible by blockShapes ${t.toString()}`);const r={x:s},o={blockShape:t,paddings:e};return R.runKernel(Ea,r,o)}const V0=P({spaceToBatchND_:W0});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function G0(n,t){const e=E(n,"x","prelu"),s=E(t,"alpha","prelu"),r={x:e,alpha:s};return R.runKernel(ka,r)}const uh=P({prelu_:G0});var $o={exports:{}},U0=$o.exports,hh;function H0(){return hh||(hh=1,(function(n){(function(t,e,s){function r(l){var c=this,u=a();c.next=function(){var h=2091639*c.s0+c.c*23283064365386963e-26;return c.s0=c.s1,c.s1=c.s2,c.s2=h-(c.c=h|0)},c.c=1,c.s0=u(" "),c.s1=u(" "),c.s2=u(" "),c.s0-=u(l),c.s0<0&&(c.s0+=1),c.s1-=u(l),c.s1<0&&(c.s1+=1),c.s2-=u(l),c.s2<0&&(c.s2+=1),u=null}function o(l,c){return c.c=l.c,c.s0=l.s0,c.s1=l.s1,c.s2=l.s2,c}function i(l,c){var u=new r(l),h=c&&c.state,d=u.next;return d.int32=function(){return u.next()*4294967296|0},d.double=function(){return d()+(d()*2097152|0)*11102230246251565e-32},d.quick=d,h&&(typeof h=="object"&&o(h,u),d.state=function(){return o(u,{})}),d}function a(){var l=4022871197,c=function(u){u=String(u);for(var h=0;h<u.length;h++){l+=u.charCodeAt(h);var d=.02519603282416938*l;l=d>>>0,d-=l,d*=l,l=d>>>0,d-=l,l+=d*4294967296}return(l>>>0)*23283064365386963e-26};return c}e&&e.exports?e.exports=i:this.alea=i})(U0,n)})($o)),$o.exports}var To={exports:{}},q0=To.exports,dh;function j0(){return dh||(dh=1,(function(n){(function(t,e,s){function r(a){var l=this,c="";l.x=0,l.y=0,l.z=0,l.w=0,l.next=function(){var h=l.x^l.x<<11;return l.x=l.y,l.y=l.z,l.z=l.w,l.w^=l.w>>>19^h^h>>>8},a===(a|0)?l.x=a:c+=a;for(var u=0;u<c.length+64;u++)l.x^=c.charCodeAt(u)|0,l.next()}function o(a,l){return l.x=a.x,l.y=a.y,l.z=a.z,l.w=a.w,l}function i(a,l){var c=new r(a),u=l&&l.state,h=function(){return(c.next()>>>0)/4294967296};return h.double=function(){do var d=c.next()>>>11,f=(c.next()>>>0)/4294967296,p=(d+f)/(1<<21);while(p===0);return p},h.int32=c.next,h.quick=h,u&&(typeof u=="object"&&o(u,c),h.state=function(){return o(c,{})}),h}e&&e.exports?e.exports=i:this.xor128=i})(q0,n)})(To)),To.exports}var Co={exports:{}},K0=Co.exports,fh;function X0(){return fh||(fh=1,(function(n){(function(t,e,s){function r(a){var l=this,c="";l.next=function(){var h=l.x^l.x>>>2;return l.x=l.y,l.y=l.z,l.z=l.w,l.w=l.v,(l.d=l.d+362437|0)+(l.v=l.v^l.v<<4^(h^h<<1))|0},l.x=0,l.y=0,l.z=0,l.w=0,l.v=0,a===(a|0)?l.x=a:c+=a;for(var u=0;u<c.length+64;u++)l.x^=c.charCodeAt(u)|0,u==c.length&&(l.d=l.x<<10^l.x>>>4),l.next()}function o(a,l){return l.x=a.x,l.y=a.y,l.z=a.z,l.w=a.w,l.v=a.v,l.d=a.d,l}function i(a,l){var c=new r(a),u=l&&l.state,h=function(){return(c.next()>>>0)/4294967296};return h.double=function(){do var d=c.next()>>>11,f=(c.next()>>>0)/4294967296,p=(d+f)/(1<<21);while(p===0);return p},h.int32=c.next,h.quick=h,u&&(typeof u=="object"&&o(u,c),h.state=function(){return o(c,{})}),h}e&&e.exports?e.exports=i:this.xorwow=i})(K0,n)})(Co)),Co.exports}var Ao={exports:{}},Z0=Ao.exports,ph;function J0(){return ph||(ph=1,(function(n){(function(t,e,s){function r(a){var l=this;l.next=function(){var u=l.x,h=l.i,d,f;return d=u[h],d^=d>>>7,f=d^d<<24,d=u[h+1&7],f^=d^d>>>10,d=u[h+3&7],f^=d^d>>>3,d=u[h+4&7],f^=d^d<<7,d=u[h+7&7],d=d^d<<13,f^=d^d<<9,u[h]=f,l.i=h+1&7,f};function c(u,h){var d,f=[];if(h===(h|0))f[0]=h;else for(h=""+h,d=0;d<h.length;++d)f[d&7]=f[d&7]<<15^h.charCodeAt(d)+f[d+1&7]<<13;for(;f.length<8;)f.push(0);for(d=0;d<8&&f[d]===0;++d);for(d==8?f[7]=-1:f[d],u.x=f,u.i=0,d=256;d>0;--d)u.next()}c(l,a)}function o(a,l){return l.x=a.x.slice(),l.i=a.i,l}function i(a,l){a==null&&(a=+new Date);var c=new r(a),u=l&&l.state,h=function(){return(c.next()>>>0)/4294967296};return h.double=function(){do var d=c.next()>>>11,f=(c.next()>>>0)/4294967296,p=(d+f)/(1<<21);while(p===0);return p},h.int32=c.next,h.quick=h,u&&(u.x&&o(u,c),h.state=function(){return o(c,{})}),h}e&&e.exports?e.exports=i:this.xorshift7=i})(Z0,n)})(Ao)),Ao.exports}var Eo={exports:{}},Y0=Eo.exports,mh;function Q0(){return mh||(mh=1,(function(n){(function(t,e,s){function r(a){var l=this;l.next=function(){var u=l.w,h=l.X,d=l.i,f,p;return l.w=u=u+1640531527|0,p=h[d+34&127],f=h[d=d+1&127],p^=p<<13,f^=f<<17,p^=p>>>15,f^=f>>>12,p=h[d]=p^f,l.i=d,p+(u^u>>>16)|0};function c(u,h){var d,f,p,g,m,b=[],y=128;for(h===(h|0)?(f=h,h=null):(h=h+"\0",f=0,y=Math.max(y,h.length)),p=0,g=-32;g<y;++g)h&&(f^=h.charCodeAt((g+32)%h.length)),g===0&&(m=f),f^=f<<10,f^=f>>>15,f^=f<<4,f^=f>>>13,g>=0&&(m=m+1640531527|0,d=b[g&127]^=f+m,p=d==0?p+1:0);for(p>=128&&(b[(h&&h.length||0)&127]=-1),p=127,g=512;g>0;--g)f=b[p+34&127],d=b[p=p+1&127],f^=f<<13,d^=d<<17,f^=f>>>15,d^=d>>>12,b[p]=f^d;u.w=m,u.X=b,u.i=p}c(l,a)}function o(a,l){return l.i=a.i,l.w=a.w,l.X=a.X.slice(),l}function i(a,l){a==null&&(a=+new Date);var c=new r(a),u=l&&l.state,h=function(){return(c.next()>>>0)/4294967296};return h.double=function(){do var d=c.next()>>>11,f=(c.next()>>>0)/4294967296,p=(d+f)/(1<<21);while(p===0);return p},h.int32=c.next,h.quick=h,u&&(u.X&&o(u,c),h.state=function(){return o(c,{})}),h}e&&e.exports?e.exports=i:this.xor4096=i})(Y0,n)})(Eo)),Eo.exports}var Do={exports:{}},tw=Do.exports,gh;function ew(){return gh||(gh=1,(function(n){(function(t,e,s){function r(a){var l=this,c="";l.next=function(){var h=l.b,d=l.c,f=l.d,p=l.a;return h=h<<25^h>>>7^d,d=d-f|0,f=f<<24^f>>>8^p,p=p-h|0,l.b=h=h<<20^h>>>12^d,l.c=d=d-f|0,l.d=f<<16^d>>>16^p,l.a=p-h|0},l.a=0,l.b=0,l.c=-1640531527,l.d=1367130551,a===Math.floor(a)?(l.a=a/4294967296|0,l.b=a|0):c+=a;for(var u=0;u<c.length+20;u++)l.b^=c.charCodeAt(u)|0,l.next()}function o(a,l){return l.a=a.a,l.b=a.b,l.c=a.c,l.d=a.d,l}function i(a,l){var c=new r(a),u=l&&l.state,h=function(){return(c.next()>>>0)/4294967296};return h.double=function(){do var d=c.next()>>>11,f=(c.next()>>>0)/4294967296,p=(d+f)/(1<<21);while(p===0);return p},h.int32=c.next,h.quick=h,u&&(typeof u=="object"&&o(u,c),h.state=function(){return o(c,{})}),h}e&&e.exports?e.exports=i:this.tychei=i})(tw,n)})(Do)),Do.exports}var Fo={exports:{}},nw={},sw=Object.freeze({__proto__:null,default:nw}),rw=kg(sw),ow=Fo.exports,bh;function iw(){return bh||(bh=1,(function(n){(function(t,e,s){var r=256,o=6,i=52,a="random",l=s.pow(r,o),c=s.pow(2,i),u=c*2,h=r-1,d;function f(w,I,S){var T=[];I=I==!0?{entropy:!0}:I||{};var C=b(m(I.entropy?[w,k(e)]:w??y(),3),T),N=new p(T),$=function(){for(var x=N.g(o),F=l,M=0;x<c;)x=(x+M)*r,F*=r,M=N.g(1);for(;x>=u;)x/=2,F/=2,M>>>=1;return(x+M)/F};return $.int32=function(){return N.g(4)|0},$.quick=function(){return N.g(4)/4294967296},$.double=$,b(k(N.S),e),(I.pass||S||function(x,F,M,O){return O&&(O.S&&g(O,N),x.state=function(){return g(N,{})}),M?(s[a]=x,F):x})($,C,"global"in I?I.global:this==s,I.state)}function p(w){var I,S=w.length,T=this,C=0,N=T.i=T.j=0,$=T.S=[];for(S||(w=[S++]);C<r;)$[C]=C++;for(C=0;C<r;C++)$[C]=$[N=h&N+w[C%S]+(I=$[C])],$[N]=I;(T.g=function(x){for(var F,M=0,O=T.i,L=T.j,B=T.S;x--;)F=B[O=h&O+1],M=M*r+B[h&(B[O]=B[L=h&L+F])+(B[L]=F)];return T.i=O,T.j=L,M})(r)}function g(w,I){return I.i=w.i,I.j=w.j,I.S=w.S.slice(),I}function m(w,I){var S=[],T=typeof w,C;if(I&&T=="object")for(C in w)try{S.push(m(w[C],I-1))}catch{}return S.length?S:T=="string"?w:w+"\0"}function b(w,I){for(var S=w+"",T,C=0;C<S.length;)I[h&C]=h&(T^=I[h&C]*19)+S.charCodeAt(C++);return k(I)}function y(){try{var w;return d&&(w=d.randomBytes)?w=w(r):(w=new Uint8Array(r),(t.crypto||t.msCrypto).getRandomValues(w)),k(w)}catch{var I=t.navigator,S=I&&I.plugins;return[+new Date,t,S,t.screen,k(e)]}}function k(w){return String.fromCharCode.apply(0,w)}if(b(s.random(),e),n.exports){n.exports=f;try{d=rw}catch{}}else s["seed"+a]=f})(typeof self<"u"?self:ow,[],Math)})(Fo)),Fo.exports}var pl,yh;function aw(){if(yh)return pl;yh=1;var n=H0(),t=j0(),e=X0(),s=J0(),r=Q0(),o=ew(),i=iw();return i.alea=n,i.xor128=t,i.xorwow=e,i.xorshift7=s,i.xor4096=r,i.tychei=o,pl=i,pl}var ml=aw();/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class wh{constructor(t,e,s,r,o){this.mean=t,this.stdDev=e,this.dtype=s,this.nextVal=NaN,this.truncated=r,this.truncated&&(this.upper=this.mean+this.stdDev*2,this.lower=this.mean-this.stdDev*2);const i=o||Math.random();this.random=ml.alea(i.toString())}nextValue(){if(!isNaN(this.nextVal)){const r=this.nextVal;return this.nextVal=NaN,r}let t,e,s=!1;for(;!s;){let r,o,i;do r=2*this.random()-1,o=2*this.random()-1,i=r*r+o*o;while(i>=1||i===0);const a=Math.sqrt(-2*Math.log(i)/i);t=this.mean+this.stdDev*r*a,e=this.mean+this.stdDev*o*a,(!this.truncated||this.isValidTruncated(t))&&(s=!0)}return(!this.truncated||this.isValidTruncated(e))&&(this.nextVal=this.convertValue(e)),this.convertValue(t)}convertValue(t){return this.dtype==null||this.dtype==="float32"?t:Math.round(t)}isValidTruncated(t){return t<=this.upper&&t>=this.lower}}class lw{constructor(t=0,e=1,s,r){if(this.canReturnFloat=()=>this.dtype==null||this.dtype==="float32",this.min=t,this.range=e-t,this.dtype=s,r==null&&(r=Math.random()),typeof r=="number"&&(r=r.toString()),!this.canReturnFloat()&&this.range<=1)throw new Error(`The difference between ${t} - ${e} <= 1 and dtype is not float`);this.random=ml.alea(r)}convertValue(t){return this.canReturnFloat()?t:Math.round(t)}nextValue(){return this.convertValue(this.min+this.range*this.random())}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function cw(n,t=0,e=1,s,r){if(dn(n),s!=null&&s==="bool")throw new Error(`Unsupported data type ${s}`);const o=new wh(t,e,s,!1,r),i=mt(n,s);for(let a=0;a<i.values.length;a++)i.values[a]=o.nextValue();return i.toTensor()}const uw=P({randomNormal_:cw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function hw(n,t=0,e=1,s="float32",r){dn(n);const o=mt(n,s),i=new lw(t,e,null,r);for(let a=0;a<o.values.length;a++)o.values[a]=i.nextValue();return o.toTensor()}const sr=P({randomUniform_:hw});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function rr(n,t,e=1,s="float32"){if(e===0)throw new Error("Cannot have a step of zero");const r={start:n,stop:t,step:e,dtype:s};return R.runKernel(iu,{},r)}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function dw(n){const e={input:E(n,"input","real")};return R.runKernel(au,e)}const fw=P({real_:dw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function pw(n){const e={x:E(n,"x","relu")};return R.runKernel(jr,e)}const $s=P({relu_:pw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function mw(n){const e={x:E(n,"x","relu6")};return R.runKernel(Kr,e)}const gw=P({relu6_:mw});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function bw(n,t){const s={x:E(n,"x","reverse")},r={dims:t};return R.runKernel(Na,s,r)}const Mo=P({reverse_:bw});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function yw(n){const e={x:E(n,"x","round")};return R.runKernel(Xr,e)}const ww=P({round_:yw});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function kw(n){const e={x:E(n,"x","rsqrt","float32")};return R.runKernel(Zr,e)}const xw=P({rsqrt_:kw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Iw(n){const e={x:E(n,"x","selu")};return R.runKernel(Jr,e)}const Sw=P({selu_:Iw});function vw(n,t,e,s,r,o=[1,1],i="NHWC"){const a=E(n,"x","separableConv2d"),l=E(t,"depthwiseFilter","separableConv2d"),c=E(e,"pointwiseFilter","separableConv2d");let u=a,h=!1;if(a.rank===3&&(h=!0,u=_(a,[1,a.shape[0],a.shape[1],a.shape[2]])),i==="NCHW")throw new Error("separableConv2d currently does not support dataFormat NCHW; only NHWC is supported");v(u.rank===4,()=>`Error in separableConv2d: input must be rank 4, but got rank ${u.rank}.`),v(l.rank===4,()=>`Error in separableConv2d: depthwise filter must be rank 4, but got rank ${l.rank}.`),v(c.rank===4,()=>`Error in separableConv2d: pointwise filter must be rank 4, but got rank ${l.rank}.`),v(c.shape[0]===1,()=>`Error in separableConv2d: the first dimension of pointwise filter  must be 1, but got ${c.shape[0]}.`),v(c.shape[1]===1,()=>`Error in separableConv2d: the second dimension of pointwise filter must be 1, but got ${c.shape[1]}.`);const d=l.shape[2],f=l.shape[3];v(c.shape[2]===d*f,()=>`Error in separableConv2d: the third dimension of pointwise filter must be ${d*f}, but got ${c.shape[2]}.`);const p=nh(u,l,s,r,i,o),m=Is(p,c,1,"valid",i);return h?_(m,[m.shape[1],m.shape[2],m.shape[3]]):m}const Nw=P({separableConv2d_:vw});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function $w(n){const e={x:E(n,"x","sin","float32")};return R.runKernel(Yr,e)}const Tw=P({sin_:$w});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Cw(n){const e={x:E(n,"x","sinh")};return R.runKernel(Qr,e)}const Aw=P({sinh_:Cw});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ew(n,t,e){const s=E(n,"x","slice1d");return v(s.rank===1,()=>`slice1d expects a rank-1 tensor, but got a rank-${s.rank} tensor`),Bt(s,[t],[e])}const gl=P({slice1d_:Ew});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Dw(n,t,e){const s=E(n,"x","slice2d");return v(s.rank===2,()=>`slice2d expects a rank-2 tensor, but got a rank-${s.rank} tensor`),Bt(s,t,e)}const kh=P({slice2d_:Dw});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Fw(n,t,e){const s=E(n,"x","slice3d");return v(s.rank===3,()=>`slice3d expects a rank-3 tensor, but got a rank-${s.rank} tensor`),Bt(s,t,e)}const bl=P({slice3d_:Fw});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Mw(n,t,e){const s=E(n,"x","slice4d");return v(s.rank===4,()=>`slice4d expects a rank-4 tensor, but got a rank-${s.rank} tensor`),Bt(s,t,e)}const Ro=P({slice4d_:Mw});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Rw(n,t=-1){const e=E(n,"logits","softmax","float32");if(t===-1&&(t=e.rank-1),t!==e.rank-1)throw Error(`Softmax along a non-last dimension is not yet supported. Logits was rank ${e.rank} and dim was ${t}`);const s={logits:e},r={dim:t};return R.runKernel(Fa,s,r)}const xh=P({softmax_:Rw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function zw(n,t,e=0){const r={x:E(n,"x","split")},o={numOrSizeSplits:t,axis:e};return R.runKernel(Da,r,o)}const en=P({split_:zw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Lw(n,t){const e=E(n,"x","squeeze","string_or_numeric");return _(e,Cm(e.shape,t).newShape)}const zo=P({squeeze_:Lw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ow(n,t=0){const e=Ou(n,"tensors","stack","string_or_numeric");v(e.length>=1,()=>"Pass at least one tensor to tf.stack"),e.length>0&&v(t<=e[0].rank,()=>"Axis must be <= rank of the tensor");const s=e,r={axis:t};return R.runKernel(ya,s,r)}const An=P({stack_:Ow});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function _w(n,t=0){const s={x:E(n,"x","step")},r={alpha:t};return R.runKernel(io,s,r)}const Lo=P({step_:_w});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function ke(n,t){xc(n);const e=fo(n,t);if(e.length!==1)throw new Error("tensor1d() requires values to be a flat/TypedArray");return mo(n,null,e,t)}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Oo(n,t,e){if(xc(n),t!=null&&t.length!==2)throw new Error("tensor2d() requires shape to have two numbers");const s=fo(n,e);if(s.length!==2&&s.length!==1)throw new Error("tensor2d() requires values to be number[][] or flat/TypedArray");if(s.length===1&&t==null)throw new Error("tensor2d() requires shape to be provided when `values` are a flat/TypedArray");return mo(n,t,s,e)}function yl(n,t,e){const s=t.shape.length,r=s>1?t.shape[s-1]:1,o=e.length;let i=1;for(let h=r;h<o;++h)i*=e[h];const a=r<1?1:r,l=Z(t.shape)/a,c=[...it(e.slice(0,r)),1],u=Z(e);return{sliceRank:r,numUpdates:l,sliceSize:i,strides:c,outputSize:u}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Bw(n,t=0,e=1,s,r){if(dn(n),s!=null&&s==="bool")throw new Error("Unsupported data type $ { dtype }");const o=new wh(t,e,s,!0,r),i=mt(n,s);for(let a=0;a<i.values.length;a++)i.values[a]=o.nextValue();return i.toTensor()}const Ih=P({truncatedNormal_:Bw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Pw(n,t,e){const s=E(n,"x","unsortedSegmentSum"),r=E(t,"segmentIds","unsortedSegmentSum","int32");v($r(e),()=>"numSegments must be of dtype int");const o={x:s,segmentIds:r},i={numSegments:e};return R.runKernel(La,o,i)}const Ww=P({unsortedSegmentSum_:Pw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Vw(n,t=0){const e=E(n,"x","unstack","string_or_numeric");v(t>=-e.shape.length&&t<e.shape.length,()=>`Axis = ${t} is not in [-${e.shape.length}, ${e.shape.length})`);const s={value:e},r={axis:t};return R.runKernel(za,s,r)}const Ts=P({unstack_:Vw});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Gw(n,t=!0,e,s){return R.makeVariable(n,t,e,s)}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Uw(n,t){const e=[];for(let o=0;o<t.length;o++)t[o]&&e.push(o);const s=mt(n,"int32"),r=mt([e.length,n.length],"int32");for(let o=0;o<e.length;o++){const i=s.indexToLoc(e[o]),a=o*n.length;r.values.set(i,a)}return r.toTensor()}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Hw(n,t,e){const s=E(n,"x","transpose");if(t==null&&(t=s.shape.map((i,a)=>a).reverse()),v(s.rank===t.length,()=>`Error in transpose: rank of input ${s.rank} must match length of perm ${t}.`),t.forEach(i=>{v(i>=0&&i<s.rank,()=>`All entries in 'perm' must be between 0 and ${s.rank-1} but got ${t}`)}),s.rank<=1)return s.clone();const r={x:s},o={perm:t};return s.dtype==="complex64"?z(()=>{let i=fw(s),a=u0(s);return i=R.runKernel(Gs,{x:i},o),a=R.runKernel(Gs,{x:a},o),e&&(a=se(a)),po(i,a)}):R.runKernel(Gs,r,o)}const bt=P({transpose_:Hw});/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function qw(n,t){if(t==null)return n.shape.slice();if(oe(n.shape,t))return t;if(n.shape.length===t.length){const e=[];for(let s=0;s<n.shape.length;s++)t[s]==null&&n.shape[s]!=null?e.push(n.shape[s]):e.push(t[s]);return e}return t}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function jw(n,t,e,s){const r=E(n,"x","dropout");if(v(r.dtype==="float32",()=>`x has to be a floating point tensor since it's going to be scaled, but got a ${r.dtype} tensor instead.`),v(t>=0&&t<1,()=>`rate must be a float in the range [0, 1), but got ${t}.`),t===0)return n instanceof ee?r.clone():r;const o=qw(r,e),i=1-t,a=rt(cl(X(sr(o,0,1,"float32",s),i)),i);return D(r,a)}const Kw=P({dropout_:jw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Xw(n,t,e,s,r,o="NHWC",i){let a=n;n.rank===3&&(a=_(n,[1,n.shape[0],n.shape[1],n.shape[2]]));let l=t;l.rank===3&&(l=_(t,[1,t.shape[0],t.shape[1],t.shape[2]])),v(a.rank===4,()=>`Error in conv2dDerFilter: input must be rank 4, but got shape ${a.shape}.`),v(l.rank===4,()=>`Error in conv2dDerFilter: dy must be rank 4, but got shape ${l.shape}.`),v(e.length===4,()=>`Error in conv2dDerFilter: filterShape must be length 4, but got ${e}.`);const c=o==="NHWC"?a.shape[3]:a.shape[1],u=o==="NHWC"?l.shape[3]:l.shape[1];v(c===e[2],()=>`Error in conv2dDerFilter: depth of input ${c}) must match input depth in filter (${e[2]}.`),v(u===e[3],()=>`Error in conv2dDerFilter: depth of dy (${u}) must match output depth for filter (${e[3]}).`),be("conv2dDerFilter",r,i);const h={x:a,dy:l},d={strides:s,pad:r,dataFormat:o,dimRoundingMode:i,filterShape:e};return R.runKernel(Lc,h,d)}const wl=P({conv2DBackpropFilter_:Xw});/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Sh(n,t,e){if(e==null||e==="linear")return n;if(e==="relu")return D(n,Lo(t));throw new Error(`Cannot compute gradient for fused activation ${e}.`)}function vh(n,t){let e=t;const s=Yt(n.shape,t.shape);return s.length>0&&(e=st(e,s)),_(e,n.shape)}function Nh(n,t,e,s){if(t==="linear")return n;if(t==="relu")return $s(n);if(t==="elu")return al(n);if(t==="relu6")return gw(n);if(t==="prelu")return uh(n,e);if(t==="leakyrelu")return lh(n,s);if(t==="sigmoid")return xo(n);throw new Error(`Unknown fused activation ${t}.`)}const $h=(n,t)=>!(n>0)||t==="linear";/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Zw({x:n,filter:t,strides:e,pad:s,dataFormat:r="NHWC",dilations:o=[1,1],dimRoundingMode:i,bias:a,activation:l="linear",preluActivationWeights:c,leakyreluAlpha:u}){if(l=l||"linear",$h(R.state.gradientDepth,l)===!1){v(r==="NHWC",()=>`Error in fused conv2d: got dataFormat of ${r} but only NHWC is currently supported for the case of gradient depth is 0 and the activation is not linear.`);let S=Is(n,t,e,s,r,o,i);return a!=null&&(S=X(S,a)),Nh(S,l,c,u)}const h=E(n,"x","conv2d","float32"),d=E(t,"filter","conv2d","float32");let f=h,p=!1;h.rank===3&&(p=!0,f=_(h,[1,h.shape[0],h.shape[1],h.shape[2]])),v(f.rank===4,()=>`Error in fused conv2d: input must be rank 4, but got rank ${f.rank}.`),v(d.rank===4,()=>`Error in fused conv2d: filter must be rank 4, but got rank ${d.rank}.`),be("fused conv2d",s,i);const g=r==="NHWC"?f.shape[3]:f.shape[1];v(d.shape[2]===g,()=>`Error in conv2d: depth of input (${g}) must match input depth for filter ${d.shape[2]}.`),v(Ze(e,o),()=>`Error in conv2D: Either strides or dilations must be 1. Got strides ${e} and dilations '${o}'`);const m=pn(f.shape,d.shape,e,o,s,i);let b;a!=null&&(b=E(a,"bias","fused conv2d"),[b]=ne(b,h),r==="NHWC"?Ct(m.outShape,b.shape):(v(b.shape.length<=1,()=>`Error in fused conv2d: only supports scalar or 1-D Tensor bias for NCHW format but got the bias of rank-${b.shape.length}.`),v(b.shape.length===0||b.shape[0]===m.outChannels||b.shape[0]===1,()=>`Error in fused conv2d: bias shape (${b.shape}) is not compatible with the number of output channels (${m.outChannels})`)));let y;if(c!=null){const S=c.shape;if(v(S.length<=1||S.length===3,()=>`Error in fused conv2d: only supports scalar, 1-D Tensor or 3-D Tensor PReLU activation weights but got a tensor of rank-${S.length}.`),S.length===1)v(S[0]===1||S[0]===m.outChannels,()=>`Error in fused conv2d: PReLU activation weights (${S}) is not compatible with the number of output channels (${m.outChannels}).`);else if(S.length===3)try{Ct(S,m.outShape)}catch{const C=`Error in fused conv2d: PReLU activation weights (${S}) is not compatible with the output shape of the conv2d (${m.outShape}).`;throw Error(C)}y=E(c,"prelu weights","fused conv2d")}const k=(S,T)=>{v(r==="NHWC",()=>`Error in gradient of fused conv2D: got dataFormat of ${r} but only NHWC is currently supported.`);const[C,N,$,x]=T,F=Sh(S,$,l);v(ks(o),()=>`Error in gradient of fused conv2D: dilation rates greater than 1 are not yet supported in gradients. Got dilations '${o}'`);const M=il(N.shape,F,C,e,s),O=wl(N,F,C.shape,e,s),L=[M,O];if(x!=null){const B=vh(x,F);L.push(B)}return L},w={x:f,filter:d,bias:b,preluActivationWeights:y},I={strides:e,pad:s,dataFormat:r,dilations:o,dimRoundingMode:i,activation:l,leakyreluAlpha:u};return a==null?nr((T,C,N)=>{let $=R.runKernel(Ba,w,I);return N([C,T,$]),p&&($=_($,[$.shape[1],$.shape[2],$.shape[3]])),{value:$,gradFunc:k}})(f,d):nr((T,C,N,$)=>{let x=R.runKernel(Ba,w,I);return $([C,T,x,N]),p&&(x=_(x,[x.shape[1],x.shape[2],x.shape[3]])),{value:x,gradFunc:k}})(f,d,b)}const Jw=P({fusedConv2d_:Zw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Yw(n,t,e,s,r,o=[1,1],i){let a=n;n.rank===3&&(a=_(n,[1,n.shape[0],n.shape[1],n.shape[2]]));let l=t;l.rank===3&&(l=_(t,[1,t.shape[0],t.shape[1],t.shape[2]]));const c={x:a,dy:l},u={strides:s,pad:r,dimRoundingMode:i,dilations:o,filterShape:e};return R.runKernel(Vc,c,u)}const Qw=P({depthwiseConv2dNativeBackpropFilter_:Yw});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function t1(n,t,e,s,r,o=[1,1],i){let a=t,l=!1;t.rank===3&&(l=!0,a=_(t,[1,t.shape[0],t.shape[1],t.shape[2]]));const c={dy:a,filter:e},u={strides:s,pad:r,dimRoundingMode:i,dilations:o,inputShape:n},h=R.runKernel(Gc,c,u);return l?_(h,[h.shape[1],h.shape[2],h.shape[3]]):h}const e1=P({depthwiseConv2dNativeBackpropInput_:t1});/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function n1({a:n,b:t,transposeA:e=!1,transposeB:s=!1,bias:r,activation:o="linear",preluActivationWeights:i,leakyreluAlpha:a=.2}){if($h(R.state.gradientDepth,o)===!1){let x=Tt(n,t,e,s);return r!=null&&(x=X(x,r)),Nh(x,o,i,a)}let l=E(n,"a","fused matMul"),c=E(t,"b","fused matMul");[l,c]=ne(l,c);const u=e?l.shape[l.rank-2]:l.shape[l.rank-1],h=s?c.shape[c.rank-1]:c.shape[c.rank-2],d=e?l.shape[l.rank-1]:l.shape[l.rank-2],f=s?c.shape[c.rank-2]:c.shape[c.rank-1],p=l.shape.slice(0,-2),g=c.shape.slice(0,-2),m=Z(p),b=Z(g);v(u===h,()=>`Error in fused matMul: inner shapes (${u}) and (${h}) of Tensors with shapes ${l.shape} and ${c.shape} and transposeA=${e} and transposeB=${s} must match.`);const k=Ct(l.shape.slice(0,-2),c.shape.slice(0,-2)).concat([d,f]),w=e?_(l,[m,u,d]):_(l,[m,d,u]),I=s?_(c,[b,f,h]):_(c,[b,h,f]);let S;r!=null&&(S=E(r,"bias","fused matMul"),[S]=ne(S,l),Ct(k,S.shape));let T;i!=null&&(T=E(i,"prelu weights","fused matMul"));const C=(x,F)=>{const[M,O,L,B]=F,G=Sh(_(x,L.shape),L,o);let W,V;if(!e&&!s?(W=Tt(G,O,!1,!0),V=Tt(M,G,!0,!1)):!e&&s?(W=Tt(G,O,!1,!1),V=Tt(G,M,!0,!1)):e&&!s?(W=Tt(O,G,!1,!0),V=Tt(M,G,!1,!1)):(W=Tt(O,G,!0,!0),V=Tt(G,M,!0,!0)),r!=null){const U=vh(B,G);return[W,V,U]}else return[W,V]},N={a:w,b:I,bias:S,preluActivationWeights:T},$={transposeA:e,transposeB:s,activation:o,leakyreluAlpha:a};return r==null?nr((F,M,O)=>{const L=R.runKernel(_a,N,$);return O([F,M,L]),{value:_(L,k),gradFunc:C}})(w,I):nr((F,M,O,L)=>{const B=R.runKernel(_a,N,$);return L([F,M,B,O]),{value:_(B,k),gradFunc:C}})(w,I,S)}const Th=P({fusedMatMul_:n1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function s1(n,t,e,s,r="bilinear",o=0){const i=E(n,"image","cropAndResize"),a=E(t,"boxes","cropAndResize","float32"),l=E(e,"boxInd","cropAndResize","int32"),c=a.shape[0];v(i.rank===4,()=>`Error in cropAndResize: image must be rank 4,but got rank ${i.rank}.`),v(a.rank===2&&a.shape[1]===4,()=>`Error in cropAndResize: boxes must be have size [${c},4] but had shape ${a.shape}.`),v(l.rank===1&&l.shape[0]===c,()=>`Error in cropAndResize: boxInd must be have size [${c}] but had shape ${a.shape}.`),v(s.length===2,()=>`Error in cropAndResize: cropSize must be of length 2, but got length ${s.length}.`),v(s[0]>=1&&s[1]>=1,()=>`cropSize must be atleast [1,1], but was ${s}`),v(r==="bilinear"||r==="nearest",()=>`method must be bilinear or nearest, but was ${r}`);const u={image:i,boxes:a,boxInd:l},h={method:r,extrapolationValue:o,cropSize:s};return R.runKernel(Pc,u,h)}const r1=P({cropAndResize_:s1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function o1(n){const t=E(n,"image","flipLeftRight","float32");v(t.rank===4,()=>`Error in flipLeftRight: image must be rank 4,but got rank ${t.rank}.`);const e={image:t};return R.runKernel(Kc,e,{})}const i1=P({flipLeftRight_:o1});/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function a1(n){const t=E(n,"image","grayscaleToRGB"),e=t.rank-1,s=t.shape[e];v(t.rank>=2,()=>`Error in grayscaleToRGB: images must be at least rank 2, but got rank ${t.rank}.`),v(s===1,()=>`Error in grayscaleToRGB: last dimension of a grayscale image should be size 1, but got size ${s}.`);const r=new Array(t.rank);return r.fill(1,0,e),r[e]=3,tn(t,r)}const l1=P({grayscaleToRGB_:a1});/**
 * @license
 * Copyright 2023 Google LLC.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function c1(n){const t=E(n,"image","RGBToGrayscale"),e=t.rank-1,s=t.shape[e];v(t.rank>=2,()=>`Error in RGBToGrayscale: images must be at least rank 2, but got rank ${t.rank}.`),v(s===3,()=>`Error in RGBToGrayscale: last dimension of an RGB image should be size 3, but got size ${s}.`);const r=t.dtype,o=Q(t,"float32"),i=ke([.2989,.587,.114]);let a;switch(t.rank){case 2:a=Qs("ij,j->i",o,i);break;case 3:a=Qs("ijk,k->ij",o,i);break;case 4:a=Qs("ijkl,l->ijk",o,i);break;case 5:a=Qs("ijklm,m->ijkl",o,i);break;case 6:a=Qs("ijklmn,n->ijklm",o,i);break;default:throw new Error("Not a valid tensor rank.")}return a=we(a,-1),Q(a,r)}const u1=P({rgbToGrayscale_:c1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function h1(n,t,e=0,s=.5){const r=E(n,"image","rotateWithOffset","float32");v(r.rank===4,()=>`Error in rotateWithOffset: image must be rank 4,but got rank ${r.rank}.`);const o={image:r},i={radians:t,fillValue:e,center:s};return R.runKernel(fu,o,i)}const d1=P({rotateWithOffset_:h1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Cs(n,t,e,s,r,o){s==null&&(s=.5),r==null&&(r=Number.NEGATIVE_INFINITY),o==null&&(o=0);const i=n.shape[0];return e=Math.min(e,i),v(0<=s&&s<=1,()=>`iouThreshold must be in [0, 1], but was '${s}'`),v(n.rank===2,()=>`boxes must be a 2D tensor, but was of rank '${n.rank}'`),v(n.shape[1]===4,()=>`boxes must have 4 columns, but 2nd dimension was ${n.shape[1]}`),v(t.rank===1,()=>"scores must be a 1D tensor"),v(t.shape[0]===i,()=>`scores has incompatible shape with boxes. Expected ${i}, but was ${t.shape[0]}`),v(0<=o&&o<=1,()=>`softNmsSigma must be in [0, 1], but was '${o}'`),{maxOutputSize:e,iouThreshold:s,scoreThreshold:r,softNmsSigma:o}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function f1(n,t,e,s=.5,r=Number.NEGATIVE_INFINITY){const o=E(n,"boxes","nonMaxSuppression","float32"),i=E(t,"scores","nonMaxSuppression","float32"),a=Cs(o,i,e,s,r);e=a.maxOutputSize,s=a.iouThreshold,r=a.scoreThreshold;const l={maxOutputSize:e,iouThreshold:s,scoreThreshold:r};return R.runKernel(nu,{boxes:o,scores:i},l)}const p1=P({nonMaxSuppression_:f1});/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function m1(n,t,e){const s=g1(n,t,e),r=s<0?-(s+1):s;n.splice(r,0,t)}function g1(n,t,e){return y1(n,t,e||b1)}function b1(n,t){return n>t?1:n<t?-1:0}function y1(n,t,e){let s=0,r=n.length,o=0,i=!1;for(;s<r;){o=s+(r-s>>>1);const a=e(t,n[o]);a>0?s=o+1:(r=o,i=!a)}return i?s:-s-1}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ch(n,t,e,s,r){return kl(n,t,e,s,r,0)}function Ah(n,t,e,s,r,o){return kl(n,t,e,s,r,0,!1,o,!0)}function Eh(n,t,e,s,r,o){return kl(n,t,e,s,r,o,!0)}function kl(n,t,e,s,r,o,i=!1,a=!1,l=!1){const c=[];for(let m=0;m<t.length;m++)t[m]>r&&c.push({score:t[m],boxIndex:m,suppressBeginIndex:0});c.sort(Dh);const u=o>0?-.5/o:0,h=[],d=[];for(;h.length<e&&c.length>0;){const m=c.pop(),{score:b,boxIndex:y,suppressBeginIndex:k}=m;if(b<r)break;let w=!1;for(let I=h.length-1;I>=k;--I){const S=w1(n,y,h[I]);if(S>=s){w=!0;break}if(m.score=m.score*k1(s,u,S),m.score<=r)break}m.suppressBeginIndex=h.length,w||(m.score===b?(h.push(y),d.push(m.score)):m.score>r&&m1(c,m,Dh))}const f=h.length,p=e-f;a&&p>0&&(h.push(...new Array(p).fill(0)),d.push(...new Array(p).fill(0)));const g={selectedIndices:h};return i&&(g.selectedScores=d),l&&(g.validOutputs=f),g}function w1(n,t,e){const s=n.subarray(t*4,t*4+4),r=n.subarray(e*4,e*4+4),o=Math.min(s[0],s[2]),i=Math.min(s[1],s[3]),a=Math.max(s[0],s[2]),l=Math.max(s[1],s[3]),c=Math.min(r[0],r[2]),u=Math.min(r[1],r[3]),h=Math.max(r[0],r[2]),d=Math.max(r[1],r[3]),f=(a-o)*(l-i),p=(h-c)*(d-u);if(f<=0||p<=0)return 0;const g=Math.max(o,c),m=Math.max(i,u),b=Math.min(a,h),y=Math.min(l,d),k=Math.max(b-g,0)*Math.max(y-m,0);return k/(f+p-k)}function k1(n,t,e){const s=Math.exp(t*e*e);return e<=n?s:0}function Dh(n,t){return n.score-t.score||n.score===t.score&&t.boxIndex-n.boxIndex}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */async function x1(n,t,e,s=.5,r=Number.NEGATIVE_INFINITY){const o=E(n,"boxes","nonMaxSuppressionAsync"),i=E(t,"scores","nonMaxSuppressionAsync"),a=Cs(o,i,e,s,r);e=a.maxOutputSize,s=a.iouThreshold,r=a.scoreThreshold;const l=await Promise.all([o.data(),i.data()]),c=l[0],u=l[1],{selectedIndices:h}=Ch(c,u,e,s,r);return o!==n&&o.dispose(),i!==t&&i.dispose(),ke(h,"int32")}const I1=x1;/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function S1(n,t,e,s=.5,r=Number.NEGATIVE_INFINITY,o=0){const i=E(n,"boxes","nonMaxSuppression"),a=E(t,"scores","nonMaxSuppression"),l=Cs(i,a,e,s,r,o);e=l.maxOutputSize,s=l.iouThreshold,r=l.scoreThreshold,o=l.softNmsSigma;const c={boxes:i,scores:a},u={maxOutputSize:e,iouThreshold:s,scoreThreshold:r,softNmsSigma:o},h=R.runKernel(ru,c,u);return{selectedIndices:h[0],selectedScores:h[1]}}const v1=P({nonMaxSuppressionWithScore_:S1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */async function N1(n,t,e,s=.5,r=Number.NEGATIVE_INFINITY,o=0){const i=E(n,"boxes","nonMaxSuppressionAsync"),a=E(t,"scores","nonMaxSuppressionAsync"),l=Cs(i,a,e,s,r,o);e=l.maxOutputSize,s=l.iouThreshold,r=l.scoreThreshold,o=l.softNmsSigma;const c=await Promise.all([i.data(),a.data()]),u=c[0],h=c[1],{selectedIndices:d,selectedScores:f}=Eh(u,h,e,s,r,o);return i!==n&&i.dispose(),a!==t&&a.dispose(),{selectedIndices:ke(d,"int32"),selectedScores:ke(f)}}const $1=N1;/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function T1(n,t,e,s=.5,r=Number.NEGATIVE_INFINITY,o=!1){const i=E(n,"boxes","nonMaxSuppression"),a=E(t,"scores","nonMaxSuppression"),l=Cs(i,a,e,s,r,null),c=l.maxOutputSize,u=l.iouThreshold,h=l.scoreThreshold,d={boxes:i,scores:a},f={maxOutputSize:c,iouThreshold:u,scoreThreshold:h,padToMaxOutputSize:o},p=R.runKernel(su,d,f);return{selectedIndices:p[0],validOutputs:p[1]}}const C1=P({nonMaxSuppressionPadded_:T1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */async function A1(n,t,e,s=.5,r=Number.NEGATIVE_INFINITY,o=!1){const i=E(n,"boxes","nonMaxSuppressionAsync"),a=E(t,"scores","nonMaxSuppressionAsync"),l=Cs(i,a,e,s,r,null),c=l.maxOutputSize,u=l.iouThreshold,h=l.scoreThreshold,[d,f]=await Promise.all([i.data(),a.data()]),{selectedIndices:p,validOutputs:g}=Ah(d,f,c,u,h,o);return i!==n&&i.dispose(),a!==t&&a.dispose(),{selectedIndices:ke(p,"int32"),validOutputs:kt(g,"int32")}}const E1=A1;/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function D1(n,t,e=!1,s=!1){const r=E(n,"images","resizeBilinear");v(r.rank===3||r.rank===4,()=>`Error in resizeBilinear: x must be rank 3 or 4, but got rank ${r.rank}.`),v(t.length===2,()=>`Error in resizeBilinear: new shape must 2D, but got shape ${t}.`),v(s===!1||e===!1,()=>"Error in resizeBilinear: If halfPixelCenters is true, alignCorners must be false.");let o=r,i=!1;r.rank===3&&(i=!0,o=_(r,[1,r.shape[0],r.shape[1],r.shape[2]]));const a={images:o},l={alignCorners:e,halfPixelCenters:s,size:t},c=R.runKernel(va,a,l);return i?_(c,[c.shape[1],c.shape[2],c.shape[3]]):c}const F1=P({resizeBilinear_:D1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function M1(n,t,e=!1,s=!1){const r=E(n,"images","resizeNearestNeighbor");v(r.rank===3||r.rank===4,()=>`Error in resizeNearestNeighbor: x must be rank 3 or 4, but got rank ${r.rank}.`),v(t.length===2,()=>`Error in resizeNearestNeighbor: new shape must 2D, but got shape ${t}.`),v(r.dtype==="float32"||r.dtype==="int32",()=>"`images` must have `int32` or `float32` as dtype"),v(s===!1||e===!1,()=>"Error in resizeNearestNeighbor: If halfPixelCenters is true, alignCorners must be false.");let o=r,i=!1;r.rank===3&&(i=!0,o=_(r,[1,r.shape[0],r.shape[1],r.shape[2]]));const a={images:o},l={alignCorners:e,halfPixelCenters:s,size:t},c=R.runKernel(Sa,a,l);return i?_(c,[c.shape[1],c.shape[2],c.shape[3]]):c}const R1=P({resizeNearestNeighbor_:M1});/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function z1(n,t="binary",e=!1,s=.5){const r=E(n,"image","threshold"),o=.2989,i=.587,a=.114,l=r.shape[0]*r.shape[1];let c=D(ke([s]),255),u,h,d,f;if(v(r.rank===3,()=>`Error in threshold: image must be rank 3,but got rank ${r.rank}.`),v(r.shape[2]===3||r.shape[2]===1,()=>`Error in threshold: image color channel must be equal to 3 or 1but got ${r.shape[2]}.`),v(r.dtype==="int32"||r.dtype==="float32",()=>`Error in dtype: image dtype must be int32 or float32,but got dtype ${r.dtype}.`),v(t==="otsu"||t==="binary",()=>`Method must be binary or otsu, but was ${t}`),r.shape[2]===3){[u,h,d]=en(r,[1,1,1],-1);const m=D(u,o),b=D(h,i),y=D(d,a);f=X(X(m,b),y)}else f=n;if(t==="otsu"){const m=uy(Q(ww(f),"int32"),Xs([]),256);c=L1(m,l)}const p=e?er(f,c):Ae(f,c);return Q(D(p,255),"int32")}function L1(n,t){let e=ke([-1]),s=ke([0]),r=ke([0]),o,i,a,l,c,u;for(let h=0;h<n.size-1;h++){o=Bt(n,0,h+1),i=Bt(n,h+1),c=rt(st(o),t),u=rt(st(i),t);const d=st(D(o,rr(0,o.size)));a=rt(d,st(o));const f=So(i.shape,o.size),p=X(rr(0,i.size),f),g=D(i,p);l=rt(st(g),st(i));const m=lt(a,l),b=lt(a,l),y=D(c,u);r=D(D(y,m),b);const k=Ae(r,s);s=ye(k,r,s),e=ye(k,ke([h]),e)}return e}const O1=P({threshold_:z1});/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function _1(n,t,e="nearest",s="constant",r=0,o){const i=E(n,"image","transform","float32"),a=E(t,"transforms","transform","float32");v(i.rank===4,()=>`Error in transform: image must be rank 4,but got rank ${i.rank}.`),v(a.rank===2&&(a.shape[0]===i.shape[0]||a.shape[0]===1)&&a.shape[1]===8,()=>"Error in transform: Input transform should be batch x 8 or 1 x 8"),v(o==null||o.length===2,()=>`Error in transform: outputShape must be [height, width] or null, but got ${o}.`);const l={image:i,transforms:a},c={interpolation:e,fillMode:s,fillValue:r,outputShape:o};return R.runKernel(du,l,c)}const B1=P({transform_:_1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function P1(n,t,e){const s=E(n,"a","bandPart");v(s.rank>=2,()=>`bandPart(): Rank must be at least 2, got ${s.rank}.`);const r=s.shape,[o,i]=s.shape.slice(-2);let a,l;typeof t=="number"?(v(t%1===0,()=>`bandPart(): numLower must be an integer, got ${t}.`),v(t<=o,()=>`bandPart(): numLower (${t}) must not be greater than the number of rows (${o}).`),a=E(t<0?o:t,"numLower","bandPart")):(v(t.dtype==="int32",()=>"bandPart(): numLower's dtype must be an int32."),a=ye(ul(t,0),o,No(t,o))),typeof e=="number"?(v(e%1===0,()=>`bandPart(): numUpper must be an integer, got ${e}.`),v(e<=i,()=>`bandPart(): numUpper (${e}) must not be greater than the number of columns (${i}).`),l=E(e<0?i:e,"numUpper","bandPart")):(v(e.dtype==="int32",()=>"bandPart(): numUpper's dtype must be an int32."),l=ye(ul(e,0),i,No(e,i)));const c=_(rr(0,o,1,"int32"),[-1,1]),u=rr(0,i,1,"int32"),h=lt(c,u),d=Ns(er(h,a),vs(h,se(l))),f=ae([o,i],s.dtype);return _(An(Ts(_(s,[-1,o,i])).map(p=>ye(d,p,f))),r)}const W1=P({bandPart_:P1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function V1(n){let t;if(Array.isArray(n)){t=!1,v(n!=null&&n.length>0,()=>"Gram-Schmidt process: input must not be null, undefined, or empty");const r=n[0].shape[0];for(let o=1;o<n.length;++o)v(n[o].shape[0]===r,()=>`Gram-Schmidt: Non-unique lengths found in the input vectors: (${n[o].shape[0]} vs. ${r})`)}else t=!0,n=en(n,n.shape[0],0).map(r=>zo(r,[0]));v(n.length<=n[0].shape[0],()=>`Gram-Schmidt: Number of vectors (${n.length}) exceeds number of dimensions (${n[0].shape[0]}).`);const e=[],s=n;for(let r=0;r<n.length;++r)e.push(R.tidy(()=>{let o=s[r];if(r>0)for(let i=0;i<r;++i){const a=D(st(D(e[i],o)),e[i]);o=lt(o,a)}return rt(o,oh(o,"euclidean"))}));return t?An(e,0):e}const G1=P({gramSchmidt_:V1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function U1(n,t=!1){if(v(n.rank>=2,()=>`qr() requires input tensor to have a rank >= 2, but got rank ${n.rank}`),n.rank===2)return Fh(n,t);{const e=n.shape.slice(0,n.shape.length-2).reduce((l,c)=>l*c),s=Ts(_(n,[e,n.shape[n.shape.length-2],n.shape[n.shape.length-1]]),0),r=[],o=[];s.forEach(l=>{const[c,u]=Fh(l,t);r.push(c),o.push(u)});const i=_(An(r,0),n.shape),a=_(An(o,0),n.shape);return[i,a]}}function Fh(n,t=!1){return R.tidy(()=>{v(n.shape.length===2,()=>`qr2d() requires a 2D Tensor, but got a ${n.shape.length}D Tensor.`);const e=n.shape[0],s=n.shape[1];let r=ih(e),o=Qn(n);const i=Oo([[1]],[1,1]);let a=Qn(i);const l=e>=s?s:e;for(let c=0;c<l;++c){const u=o,h=a,d=r;[a,o,r]=R.tidy(()=>{const f=Bt(o,[c,c],[e-c,1]),p=oh(f),g=Bt(o,[c,c],[1,1]),m=ye(Ae(g,0),Oo([[-1]]),Oo([[1]])),b=lt(g,D(m,p)),y=rt(f,b);y.shape[0]===1?a=Qn(i):a=_e([i,Bt(y,[1,0],[y.shape[0]-1,y.shape[1]])],0);const k=se(rt(Tt(m,b),p)),w=Bt(o,[c,0],[e-c,s]),I=D(k,a),S=bt(a);if(c===0)o=lt(w,Tt(I,Tt(S,w)));else{const N=lt(w,Tt(I,Tt(S,w)));o=_e([Bt(o,[0,0],[c,s]),N],0)}const T=bt(I),C=Bt(r,[0,c],[e,r.shape[1]-c]);if(c===0)r=lt(C,Tt(Tt(C,a),T));else{const N=lt(C,Tt(Tt(C,a),T));r=_e([Bt(r,[0,0],[e,c]),N],1)}return[a,o,r]}),dt([u,h,d])}return!t&&e>s&&(r=Bt(r,[0,0],[e,s]),o=Bt(o,[0,0],[s,s])),[r,o]})}const H1=P({qr_:U1});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const bn={flipLeftRight:i1,grayscaleToRGB:l1,resizeNearestNeighbor:R1,resizeBilinear:F1,rgbToGrayscale:u1,rotateWithOffset:d1,cropAndResize:r1,nonMaxSuppression:p1,nonMaxSuppressionAsync:I1,nonMaxSuppressionWithScore:v1,nonMaxSuppressionWithScoreAsync:$1,nonMaxSuppressionPadded:C1,nonMaxSuppressionPaddedAsync:E1,threshold:O1,transform:B1},q1={bandPart:W1,gramSchmidt:G1,qr:H1};/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const j1=new Map,K1=new Map;class As{getClassName(){return this.constructor.className}static fromConfig(t,e){return new t(e)}}class Ee{constructor(){this.classNameMap={}}static getMap(){return Ee.instance==null&&(Ee.instance=new Ee),Ee.instance}static register(t){Ee.getMap().classNameMap[t.className]=[t,t.fromConfig]}}function H(n,t,e){v(n.className!=null,()=>"Class being registered does not have the static className property defined."),v(typeof n.className=="string",()=>"className is required to be a string, but got type "+typeof n.className),v(n.className.length>0,()=>"Class being registered has an empty-string as its className, which is disallowed."),typeof t>"u"&&(t="Custom"),typeof e>"u"&&(e=n.className);const s=e,r=t+">"+s;return Ee.register(n),j1.set(r,n),K1.set(n,r),n}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class En extends As{minimize(t,e=!1,s){const{value:r,grads:o}=this.computeGradients(t,s);if(s!=null){const i=s.map(a=>({name:a.name,tensor:o[a.name]}));this.applyGradients(i)}else this.applyGradients(o);return dt(o),e?r:(r.dispose(),null)}get iterations(){return this.iterations_==null&&(this.iterations_=0),this.iterations_}incrementIterations(){this.iterations_=this.iterations+1}computeGradients(t,e){return b0(t,e)}dispose(){this.iterations_!=null&&dt(this.iterations_)}async saveIterations(){return this.iterations_==null&&(this.iterations_=0),{name:"iter",tensor:kt(this.iterations_,"int32")}}async getWeights(){throw new Error("getWeights() is not implemented for this optimizer yet.")}async setWeights(t){throw new Error(`setWeights() is not implemented for this optimizer class ${this.getClassName()}`)}async extractIterations(t){return this.iterations_=(await t[0].tensor.data())[0],t.slice(1)}}Object.defineProperty(En,Symbol.hasInstance,{value:n=>n.minimize!=null&&n.computeGradients!=null&&n.applyGradients!=null});/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class Mh extends En{static get className(){return"Adadelta"}constructor(t,e,s=null){super(),this.learningRate=t,this.rho=e,this.epsilon=s,this.accumulatedGrads=[],this.accumulatedUpdates=[],s==null&&(this.epsilon=R.backend.epsilon())}applyGradients(t){(Array.isArray(t)?t.map(s=>s.name):Object.keys(t)).forEach((s,r)=>{const o=R.registeredVariables[s],i=!1;this.accumulatedGrads[r]==null&&(this.accumulatedGrads[r]={originalName:`${s}/accum_grad`,variable:z(()=>wt(o).variable(i))}),this.accumulatedUpdates[r]==null&&(this.accumulatedUpdates[r]={originalName:`${s}/accum_var`,variable:z(()=>wt(o).variable(i))});const a=Array.isArray(t)?t[r].tensor:t[s];if(a==null)return;const l=this.accumulatedGrads[r].variable,c=this.accumulatedUpdates[r].variable;z(()=>{const u=X(D(l,this.rho),D(Mt(a),1-this.rho)),h=D(rt(ue(X(c,this.epsilon)),ue(X(l,this.epsilon))),a),d=X(D(c,this.rho),D(Mt(h),1-this.rho));l.assign(u),c.assign(d);const f=X(D(h,-this.learningRate),o);o.assign(f)})}),this.incrementIterations()}dispose(){this.accumulatedUpdates!=null&&(dt(this.accumulatedGrads.map(t=>t.variable)),dt(this.accumulatedUpdates.map(t=>t.variable)))}async getWeights(){const t=[...this.accumulatedGrads,...this.accumulatedUpdates];return[await this.saveIterations()].concat(t.map(e=>({name:e.originalName,tensor:e.variable})))}async setWeights(t){t=await this.extractIterations(t);const e=t.length/2,s=!1;this.accumulatedGrads=t.slice(0,e).map(r=>({originalName:r.name,variable:r.tensor.variable(s)})),this.accumulatedUpdates=t.slice(e,e*2).map(r=>({originalName:r.name,variable:r.tensor.variable(s)}))}getConfig(){return{learningRate:this.learningRate,rho:this.rho,epsilon:this.epsilon}}static fromConfig(t,e){return new t(e.learningRate,e.rho,e.epsilon)}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class Rh extends En{static get className(){return"Adagrad"}constructor(t,e=.1){super(),this.learningRate=t,this.initialAccumulatorValue=e,this.accumulatedGrads=[]}applyGradients(t){(Array.isArray(t)?t.map(s=>s.name):Object.keys(t)).forEach((s,r)=>{const o=R.registeredVariables[s];this.accumulatedGrads[r]==null&&(this.accumulatedGrads[r]={originalName:`${s}/accumulator`,variable:z(()=>So(o.shape,this.initialAccumulatorValue).variable(!1))});const i=Array.isArray(t)?t[r].tensor:t[s];if(i==null)return;const a=this.accumulatedGrads[r].variable;z(()=>{const l=X(a,Mt(i));a.assign(l);const c=X(D(rt(i,ue(X(l,R.backend.epsilon()))),-this.learningRate),o);o.assign(c)})}),this.incrementIterations()}dispose(){this.accumulatedGrads!=null&&dt(this.accumulatedGrads.map(t=>t.variable))}async getWeights(){return[await this.saveIterations()].concat(this.accumulatedGrads.map(t=>({name:t.originalName,tensor:t.variable})))}async setWeights(t){t=await this.extractIterations(t);const e=!1;this.accumulatedGrads=t.map(s=>({originalName:s.name,variable:s.tensor.variable(e)}))}getConfig(){return{learningRate:this.learningRate,initialAccumulatorValue:this.initialAccumulatorValue}}static fromConfig(t,e){return new t(e.learningRate,e.initialAccumulatorValue)}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class zh extends En{static get className(){return"Adam"}constructor(t,e,s,r=null){super(),this.learningRate=t,this.beta1=e,this.beta2=s,this.epsilon=r,this.accumulatedFirstMoment=[],this.accumulatedSecondMoment=[],z(()=>{this.accBeta1=kt(e).variable(),this.accBeta2=kt(s).variable()}),r==null&&(this.epsilon=R.backend.epsilon())}applyGradients(t){const e=Array.isArray(t)?t.map(s=>s.name):Object.keys(t);z(()=>{const s=lt(1,this.accBeta1),r=lt(1,this.accBeta2);e.forEach((o,i)=>{const a=R.registeredVariables[o],l=!1;this.accumulatedFirstMoment[i]==null&&(this.accumulatedFirstMoment[i]={originalName:`${o}/m`,variable:z(()=>wt(a).variable(l))}),this.accumulatedSecondMoment[i]==null&&(this.accumulatedSecondMoment[i]={originalName:`${o}/v`,variable:z(()=>wt(a).variable(l))});const c=Array.isArray(t)?t[i].tensor:t[o];if(c==null)return;const u=this.accumulatedFirstMoment[i].variable,h=this.accumulatedSecondMoment[i].variable,d=X(D(u,this.beta1),D(c,1-this.beta1)),f=X(D(h,this.beta2),D(Mt(c),1-this.beta2)),p=rt(d,s),g=rt(f,r);u.assign(d),h.assign(f);const m=X(D(rt(p,X(ue(g),this.epsilon)),-this.learningRate),a);a.assign(m)}),this.accBeta1.assign(D(this.accBeta1,this.beta1)),this.accBeta2.assign(D(this.accBeta2,this.beta2))}),this.incrementIterations()}dispose(){this.accBeta1.dispose(),this.accBeta2.dispose(),this.accumulatedFirstMoment!=null&&dt(this.accumulatedFirstMoment.map(t=>t.variable)),this.accumulatedSecondMoment!=null&&dt(this.accumulatedSecondMoment.map(t=>t.variable))}async getWeights(){const t=[...this.accumulatedFirstMoment,...this.accumulatedSecondMoment];return[await this.saveIterations()].concat(t.map(e=>({name:e.originalName,tensor:e.variable})))}async setWeights(t){t=await this.extractIterations(t),z(()=>{this.accBeta1.assign(Ss(this.beta1,this.iterations_+1)),this.accBeta2.assign(Ss(this.beta2,this.iterations_+1))});const e=t.length/2,s=!1;this.accumulatedFirstMoment=t.slice(0,e).map(r=>({originalName:r.name,variable:r.tensor.variable(s)})),this.accumulatedSecondMoment=t.slice(e,e*2).map(r=>({originalName:r.name,variable:r.tensor.variable(s)}))}getConfig(){return{learningRate:this.learningRate,beta1:this.beta1,beta2:this.beta2,epsilon:this.epsilon}}static fromConfig(t,e){return new t(e.learningRate,e.beta1,e.beta2,e.epsilon)}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class Lh extends En{static get className(){return"Adamax"}constructor(t,e,s,r=null,o=0){super(),this.learningRate=t,this.beta1=e,this.beta2=s,this.epsilon=r,this.decay=o,this.accumulatedFirstMoment=[],this.accumulatedWeightedInfNorm=[],z(()=>{this.iteration=kt(0).variable(),this.accBeta1=kt(e).variable()}),r==null&&(this.epsilon=R.backend.epsilon())}applyGradients(t){const e=Array.isArray(t)?t.map(s=>s.name):Object.keys(t);z(()=>{const s=lt(1,this.accBeta1),r=rt(-this.learningRate,X(D(this.iteration,this.decay),1));e.forEach((o,i)=>{const a=R.registeredVariables[o],l=!1;this.accumulatedFirstMoment[i]==null&&(this.accumulatedFirstMoment[i]={originalName:`${o}/m`,variable:wt(a).variable(l)}),this.accumulatedWeightedInfNorm[i]==null&&(this.accumulatedWeightedInfNorm[i]={originalName:`${o}/v`,variable:wt(a).variable(l)});const c=Array.isArray(t)?t[i].tensor:t[o];if(c==null)return;const u=this.accumulatedFirstMoment[i].variable,h=this.accumulatedWeightedInfNorm[i].variable,d=X(D(u,this.beta1),D(c,1-this.beta1)),f=D(h,this.beta2),p=fe(c),g=es(f,p);u.assign(d),h.assign(g);const m=X(D(rt(r,s),rt(d,X(g,this.epsilon))),a);a.assign(m)}),this.iteration.assign(X(this.iteration,1)),this.accBeta1.assign(D(this.accBeta1,this.beta1))}),this.incrementIterations()}dispose(){this.accBeta1.dispose(),this.iteration.dispose(),this.accumulatedFirstMoment!=null&&dt(this.accumulatedFirstMoment.map(t=>t.variable)),this.accumulatedWeightedInfNorm!=null&&dt(this.accumulatedWeightedInfNorm.map(t=>t.variable))}async getWeights(){throw new Error("getWeights() is not implemented for Adamax yet.")}async setWeights(t){throw new Error("setWeights() is not implemented for Adamax yet.")}getConfig(){return{learningRate:this.learningRate,beta1:this.beta1,beta2:this.beta2,epsilon:this.epsilon,decay:this.decay}}static fromConfig(t,e){return new t(e.learningRate,e.beta1,e.beta2,e.epsilon,e.decay)}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class xl extends En{static get className(){return"SGD"}constructor(t){super(),this.learningRate=t,this.setLearningRate(t)}applyGradients(t){(Array.isArray(t)?t.map(s=>s.name):Object.keys(t)).forEach((s,r)=>{const o=Array.isArray(t)?t[r].tensor:t[s];if(o==null)return;const i=R.registeredVariables[s];z(()=>{const a=X(D(this.c,o),i);i.assign(a)})}),this.incrementIterations()}setLearningRate(t){this.learningRate=t,this.c!=null&&this.c.dispose(),this.c=Ke(kt(-t))}dispose(){this.c.dispose()}async getWeights(){return[await this.saveIterations()]}async setWeights(t){if(t=await this.extractIterations(t),t.length!==0)throw new Error("SGD optimizer does not have settable weights.")}getConfig(){return{learningRate:this.learningRate}}static fromConfig(t,e){return new t(e.learningRate)}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class Oh extends xl{static get className(){return"Momentum"}constructor(t,e,s=!1){super(t),this.learningRate=t,this.momentum=e,this.useNesterov=s,this.accumulations=[],this.m=kt(this.momentum)}applyGradients(t){(Array.isArray(t)?t.map(s=>s.name):Object.keys(t)).forEach((s,r)=>{const o=R.registeredVariables[s];this.accumulations[r]==null&&(this.accumulations[r]={originalName:`${s}/momentum`,variable:z(()=>wt(o).variable(!1))});const i=this.accumulations[r].variable,a=Array.isArray(t)?t[r].tensor:t[s];a!=null&&z(()=>{let l;const c=X(D(this.m,i),a);this.useNesterov?l=X(D(this.c,X(a,D(c,this.m))),o):l=X(D(this.c,c),o),i.assign(c),o.assign(l)})}),this.incrementIterations()}dispose(){this.m.dispose(),this.accumulations!=null&&dt(this.accumulations.map(t=>t.variable))}setMomentum(t){this.momentum=t}async getWeights(){return[await this.saveIterations()].concat(this.accumulations.map(t=>({name:t.originalName,tensor:t.variable})))}async setWeights(t){t=await this.extractIterations(t);const e=!1;this.accumulations=t.map(s=>({originalName:s.name,variable:s.tensor.variable(e)}))}getConfig(){return{learningRate:this.learningRate,momentum:this.momentum,useNesterov:this.useNesterov}}static fromConfig(t,e){return new t(e.learningRate,e.momentum,e.useNesterov)}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class _h extends En{static get className(){return"RMSProp"}constructor(t,e=.9,s=0,r=null,o=!1){if(super(),this.learningRate=t,this.decay=e,this.momentum=s,this.epsilon=r,this.accumulatedMeanSquares=[],this.accumulatedMoments=[],this.accumulatedMeanGrads=[],this.centered=o,r==null&&(this.epsilon=R.backend.epsilon()),t==null)throw new Error("learningRate for RMSPropOptimizer must be defined.")}applyGradients(t){(Array.isArray(t)?t.map(s=>s.name):Object.keys(t)).forEach((s,r)=>{const o=R.registeredVariables[s],i=!1;this.accumulatedMeanSquares[r]==null&&(this.accumulatedMeanSquares[r]={originalName:`${s}/rms`,variable:z(()=>wt(o).variable(i))}),this.accumulatedMoments[r]==null&&(this.accumulatedMoments[r]={originalName:`${s}/momentum`,variable:z(()=>wt(o).variable(i))}),this.accumulatedMeanGrads[r]==null&&this.centered&&(this.accumulatedMeanGrads[r]={originalName:`${s}/mg`,variable:z(()=>wt(o).variable(i))});const a=Array.isArray(t)?t[r].tensor:t[s];if(a==null)return;const l=this.accumulatedMeanSquares[r].variable,c=this.accumulatedMoments[r].variable;z(()=>{const u=X(D(l,this.decay),D(Mt(a),1-this.decay));if(this.centered){const h=this.accumulatedMeanGrads[r].variable,d=X(D(h,this.decay),D(a,1-this.decay)),f=rt(D(a,this.learningRate),ue(lt(u,X(Mt(d),this.epsilon)))),p=X(D(c,this.momentum),f);l.assign(u),h.assign(d),c.assign(p);const g=lt(o,p);o.assign(g)}else{const h=X(D(l,this.decay),D(Mt(a),1-this.decay)),d=X(D(c,this.momentum),rt(D(a,this.learningRate),ue(X(h,this.epsilon))));l.assign(h),c.assign(d);const f=lt(o,d);o.assign(f)}})}),this.incrementIterations()}dispose(){this.accumulatedMeanSquares!=null&&dt(this.accumulatedMeanSquares.map(t=>t.variable)),this.accumulatedMeanGrads!=null&&this.centered&&dt(this.accumulatedMeanGrads.map(t=>t.variable)),this.accumulatedMoments!=null&&dt(this.accumulatedMoments.map(t=>t.variable))}async getWeights(){const t=[...this.accumulatedMeanSquares,...this.accumulatedMoments];return this.centered&&t.push(...this.accumulatedMeanGrads),[await this.saveIterations()].concat(t.map(e=>({name:e.originalName,tensor:e.variable})))}async setWeights(t){t=await this.extractIterations(t);const e=this.centered?t.length/3:t.length/2,s=!1;this.accumulatedMeanSquares=t.slice(0,e).map(r=>({originalName:r.name,variable:r.tensor.variable(s)})),this.accumulatedMoments=t.slice(e,e*2).map(r=>({originalName:r.name,variable:r.tensor.variable(s)})),this.centered&&(this.accumulatedMeanGrads=t.slice(e*2,e*3).map(r=>({originalName:r.name,variable:r.tensor.variable(s)})))}getConfig(){return{learningRate:this.learningRate,decay:this.decay,momentum:this.momentum,epsilon:this.epsilon,centered:this.centered}}static fromConfig(t,e){return new t(e.learningRate,e.decay,e.momentum,e.epsilon,e.centered)}}/**
 * @license
 * Copyright 2022 Google LLC.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const X1=[Mh,Rh,zh,Lh,Oh,_h,xl];function Z1(){for(const n of X1)H(n)}/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Bh(n,t,e,s){i(n),e=e??0,s=s??1,a(e,s);let r=0;const o=l=>(l.then(c=>{const u=e+ ++r/n.length*(s-e);return t(u),c}),l);function i(l){v(l!=null&&Array.isArray(l)&&l.length>0,()=>"promises must be a none empty array")}function a(l,c){v(l>=0&&l<=1,()=>`Progress fraction must be in range [0, 1], but got startFraction ${l}`),v(c>=0&&c<=1,()=>`Progress fraction must be in range [0, 1], but got endFraction ${c}`),v(c>=l,()=>`startFraction must be no more than endFraction, but got startFraction ${l} and endFraction ${c}`)}return Promise.all(n.map(o))}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */async function J1(n,t){t==null&&(t={});const e=t.fetchFunc==null?gt().platform.fetch:t.fetchFunc,s=n.map(h=>e(h,t.requestInit,{isBinary:!0})),a=(t.onProgress==null?await Promise.all(s):await Bh(s,t.onProgress,0,.5)).map(h=>h.arrayBuffer());return t.onProgress==null?await Promise.all(a):await Bh(a,t.onProgress,.5,1)}function Y1(n,t){var e;const s=t.fetchFunc==null?gt().platform.fetch:t.fetchFunc;let r=0,o;return(e=t.onProgress)===null||e===void 0||e.call(t,0),new ReadableStream({pull:async i=>{for(var a;r<n.length;){o||(o=(await s(n[r],t.requestInit,{isBinary:!0})).body.getReader());const{done:l,value:c}=await o.read();if(l){r++,o=void 0,(a=t.onProgress)===null||a===void 0||a.call(t,r/n.length);continue}i.enqueue(c);return}i.close()}})}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Q1="application/octet-stream",tk="application/json";class Il{constructor(t,e){if(this.DEFAULT_METHOD="POST",e==null&&(e={}),this.weightPathPrefix=e.weightPathPrefix,this.weightUrlConverter=e.weightUrlConverter,e.fetchFunc!=null?(v(typeof e.fetchFunc=="function",()=>"Must pass a function that matches the signature of `fetch` (see https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API)"),this.fetch=e.fetchFunc):this.fetch=gt().platform.fetch,v(t!=null&&t.length>0,()=>"URL path for http must not be null, undefined or empty."),Array.isArray(t)&&v(t.length===2,()=>`URL paths for http must have a length of 2, (actual length is ${t.length}).`),this.path=t,e.requestInit!=null&&e.requestInit.body!=null)throw new Error("requestInit is expected to have no pre-existing body, but has one.");this.requestInit=e.requestInit||{},this.loadOptions=e}async save(t){if(t.modelTopology instanceof ArrayBuffer)throw new Error("BrowserHTTPRequest.save() does not support saving model topology in binary formats yet.");const e=Object.assign({method:this.DEFAULT_METHOD},this.requestInit);e.body=new FormData;const s=[{paths:["./model.weights.bin"],weights:t.weightSpecs}],r=sb(t,s);if(e.body.append("model.json",new Blob([JSON.stringify(r)],{type:tk}),"model.json"),t.weightData!=null){const i=Nn.join(t.weightData);e.body.append("model.weights.bin",new Blob([i],{type:Q1}),"model.weights.bin")}const o=await this.fetch(this.path,e);if(o.ok)return{modelArtifactsInfo:Ja(t),responses:[o]};throw new Error(`BrowserHTTPRequest.save() failed due to HTTP response status ${o.status}.`)}async loadModelJSON(){const t=await this.fetch(this.path,this.requestInit);if(!t.ok)throw new Error(`Request to ${this.path} failed with status code ${t.status}. Please verify this URL points to the model JSON of the model to load.`);let e;try{e=await t.json()}catch{let i=`Failed to parse model JSON of response from ${this.path}.`;throw this.path.endsWith(".pb")?i+=" Your path contains a .pb file extension. Support for .pb models have been removed in TensorFlow.js 1.0 in favor of .json models. You can re-convert your Python TensorFlow model using the TensorFlow.js 1.0 conversion scripts or you can convert your.pb models with the 'pb2json'NPM script in the tensorflow/tfjs-converter repository.":i+=" Please make sure the server is serving valid JSON for this request.",new Error(i)}const s=e.modelTopology,r=e.weightsManifest;if(s==null&&r==null)throw new Error(`The JSON from HTTP path ${this.path} contains neither model topology or manifest for weights.`);return e}async load(){if(this.loadOptions.streamWeights)return this.loadStream();const t=await this.loadModelJSON();return ob(t,e=>this.loadWeights(e))}async loadStream(){const t=await this.loadModelJSON(),e=await this.getWeightUrls(t.weightsManifest),s=Vu(t.weightsManifest),r=()=>Y1(e,this.loadOptions);return Object.assign(Object.assign({},t),{weightSpecs:s,getWeightStream:r})}async getWeightUrls(t){const e=Array.isArray(this.path)?this.path[1]:this.path,[s,r]=ek(e),o=this.weightPathPrefix||s,i=[],a=[];for(const l of t)for(const c of l.paths)this.weightUrlConverter!=null?a.push(this.weightUrlConverter(c)):i.push(o+c+r);return this.weightUrlConverter&&i.push(...await Promise.all(a)),i}async loadWeights(t){const e=await this.getWeightUrls(t),s=Vu(t),r=await J1(e,this.loadOptions);return[s,r]}}Il.URL_SCHEME_REGEX=/^https?:\/\//;function ek(n){const t=n.lastIndexOf("/"),e=n.lastIndexOf("?"),s=n.substring(0,t),r=e>t?n.substring(e):"";return[s+"/",r]}function Ph(n){return n.match(Il.URL_SCHEME_REGEX)!=null}const Wh=(n,t)=>{if(typeof fetch>"u"&&(t==null||t.fetchFunc==null))return null;{let e=!0;if(Array.isArray(n)?e=n.every(s=>Ph(s)):e=Ph(n),e)return Vh(n,t)}return null};Jt.registerSaveRouter(Wh),Jt.registerLoadRouter(Wh);function Vh(n,t){return new Il(n,t)}function nk(n,t){return Vh(n,t)}function sk(n,t){const e=n.shape.length,s=t.shape.length;if(e<1)throw new Error(`tf.gatherND() expects the input to be rank 1 or higher, but the rank was ${e}.`);if(s<1)throw new Error(`tf.gatherND() expects the indices to be rank 1 or higher, but the rank was ${s}.`);if(t.dtype!=="int32")throw new Error(`tf.gatherND() expects the indices to be int32 type, but the dtype was ${t.dtype}.`);if(t.shape[s-1]>e)throw new Error(`index innermost dimension length must be <= tensor rank; saw: ${t.shape[s-1]} vs. ${e}`);if(Z(n.shape)===0)throw new Error(`Requested more than 0 entries, but input is empty. Input shape: ${n.shape}.`);const r=t.shape,o=r[r.length-1];let i=1;for(let h=0;h<r.length-1;++h)i*=r[h];const a=n.shape,l=r.slice();l.pop();let c=1;for(let h=o;h<e;++h)c*=a[h],l.push(a[h]);const u=[...it(n.shape).map(h=>h/c),1].slice(0,o);return[l,i,c,u]}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Sl=-2,rk=-1;function ok(n,t,e){const s=n.shape.length;v(s===t.length,()=>`Error in slice${s}D: Length of begin ${t} must match the rank of the array (${s}).`),v(s===e.length,()=>`Error in slice${s}D: Length of size ${e} must match the rank of the array (${s}).`);for(let r=0;r<s;++r)v(t[r]+e[r]<=n.shape[r],()=>`Error in slice${s}D: begin[${r}] + size[${r}] (${t[r]+e[r]}) would overflow input.shape[${r}] (${n.shape[r]})`)}function ik(n,t,e){const s=[];for(let r=0;r<n.length;r++)s[r]=Math.ceil((t[r]-n[r])/e[r]);return s}function ak(n,t,e){let s=e.length;for(let r=0;r<e.length;r++)if(e[r]>1){s=r;break}for(let r=s+1;r<e.length;r++)if(t[r]>0||e[r]!==n[r])return!1;return!0}function lk(n,t){let e=n.length>0?n[n.length-1]:1;for(let s=0;s<n.length-1;s++)e+=n[s]*t[s];return e}function Gh(n,t,e){let s;const r=n.shape.length;typeof t=="number"?s=[t,...new Array(r-1).fill(0)]:t.length<r?s=t.concat(new Array(r-t.length).fill(0)):s=t.slice(),s.forEach(i=>{v(i!==-1,()=>"slice() does not support negative begin indexing.")});let o;return e==null?o=new Array(r).fill(-1):typeof e=="number"?o=[e,...new Array(r-1).fill(-1)]:e.length<r?o=e.concat(new Array(r-e.length).fill(-1)):o=e,o=o.map((i,a)=>i>=0?i:(v(i===-1,()=>`Negative size values should be exactly -1 but got ${i} for the slice() size at index ${a}.`),n.shape[a]-s[a])),[s,o]}function ck(n,t,e,s,r,o,i,a,l){let c;if(s==null?(c=new Array(t.length),c.fill(1)):c=s,i!=null&&(i&i-1)!==0)throw new Error("Multiple ellipses in slice is not allowed.");let u=!1;const h={dims:c.length,numAddAxisAfterEllipsis:0,begin:t.slice(),end:e.slice(),strides:c.slice(),beginMask:r,endMask:o,ellipsisMask:i,newAxisMask:a,shrinkAxisMask:l};for(let k=0;k<h.dims;k++)u&&(1<<k&a)!==0&&h.numAddAxisAfterEllipsis++,1<<k&i&&(u=!0);u||(h.ellipsisMask|=1<<h.dims,h.dims++);const d={dims:n.length,beginMask:0,endMask:0,beginValid:!1,endValid:!1};uk(h,d);let f=!0,p=!0,g=!0;const m=[],b=[];for(let k=0;k<n.length;++k){if(d.strides[k]===0)throw Error(`strides[${k}] must be non-zero`);const w=!!(d.shrinkAxisMask&1<<k),I=n[k];if(I===-1){m.push(w?1:-1);continue}const S=[d.beginMask&1<<k,d.endMask&1<<k],T=[d.strides[k]>0?0:-1,d.strides[k]>0?I:I-1];if(w&&d.strides[k]<=0)throw Error("only stride 1 allowed on non-range indexing.");g=g&&d.strides[k]===1;const C=!!(d.beginMask&1<<k&&d.endMask&1<<k);if(d.beginValid&&d.endValid){if(w){const F=d.begin[k]<0?I+d.begin[k]:d.begin[k];if(d.begin[k]=F,d.end[k]=d.begin[k]+1,F<0||F>=I)throw Error(`slice index ${d.begin[k]} of dimension ${k} out of bounds.`)}else d.begin[k]=Uh(d.begin[k],0,d.strides[k],I,S,T),d.end[k]=Uh(d.end[k],1,d.strides[k],I,S,T);const x=d.strides[k]===1&&d.begin[k]===0&&d.end[k]===I;f=f&&x,p=p&&(k===0&&d.strides[k]===1||x)}else f=f&&d.strides[k]===1&&C,p=p&&(k===0&&d.strides[k]===1||C);let N,$=!1;if(d.beginValid&&d.endValid?(N=d.end[k]-d.begin[k],$=!0):w?(N=1,$=!0):C&&I>=0&&(d.strides[k]<0?N=-I:N=I,$=!0),$){let x;N===0||N<0!=d.strides[k]<0?x=0:x=Math.trunc(N/d.strides[k])+(N%d.strides[k]!==0?1:0),m.push(x)}else m.push(-1)}for(let k=0;k<d.finalShapeGatherIndices.length;++k){const w=d.finalShapeGatherIndices[k];w>=0?b.push(m[w]):w===Sl&&b.push(1)}return{finalShapeSparse:b.filter((k,w)=>d.finalShapeGatherIndices[w]!==Sl),finalShape:b,isIdentity:f,sliceDim0:p,isSimpleSlice:g,begin:d.begin,end:d.end,strides:d.strides}}function uk(n,t){t.beginMask=0,t.endMask=0,t.shrinkAxisMask=0;let e=0;t.beginValid=n.begin!=null,t.endValid=n.end!=null,t.begin=new Array(t.dims),t.end=new Array(t.dims),t.strides=new Array(t.dims),t.finalShapeGatherIndices=[],t.finalShapeGatherIndicesSparse=[],t.inputShapeGatherIndicesSparse=new Array(t.dims);for(let s=0;s<n.dims;s++)if(1<<s&n.ellipsisMask){const r=Math.min(t.dims-(n.dims-s)+1+n.numAddAxisAfterEllipsis,t.dims);for(;e<r;e++)t.begin[e]=0,t.end[e]=0,t.strides[e]=1,t.beginMask|=1<<e,t.endMask|=1<<e,t.finalShapeGatherIndices.push(e),t.finalShapeGatherIndicesSparse.push(-1),t.inputShapeGatherIndicesSparse[e]=s}else if(1<<s&n.newAxisMask)t.finalShapeGatherIndices.push(Sl),t.finalShapeGatherIndicesSparse.push(-1);else{if(e===t.begin.length)throw Error(`Index out of range using input dim ${e}; input has only ${t.dims} dims, ${t.begin.length}.`);n.begin!=null&&(t.begin[e]=n.begin[s]),n.end!=null&&(t.end[e]=n.end[s]),t.strides[e]=n.strides[s],n.beginMask&1<<s&&(t.beginMask|=1<<e),n.endMask&1<<s&&(t.endMask|=1<<e),n.shrinkAxisMask&1<<s?(t.finalShapeGatherIndices.push(rk),t.finalShapeGatherIndicesSparse.push(-1),t.shrinkAxisMask|=1<<e):(t.finalShapeGatherIndices.push(e),t.finalShapeGatherIndicesSparse.push(s)),t.inputShapeGatherIndicesSparse[e]=s,e++}}function Uh(n,t,e,s,r,o){if(r[t])return e>0?o[t]:o[t+1&1];{const i=n<0?s+n:n;return i<o[0]?o[0]:i>o[1]?o[1]:i}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class hk{static sgd(t){return new xl(t)}static momentum(t,e,s=!1){return new Oh(t,e,s)}static rmsprop(t,e=.9,s=0,r=null,o=!1){return new _h(t,e,s,r,o)}static adam(t=.001,e=.9,s=.999,r=null){return new zh(t,e,s,r)}static adadelta(t=.001,e=.95,s=null){return new Mh(t,e,s)}static adamax(t=.002,e=.9,s=.999,r=null,o=0){return new Lh(t,e,s,r,o)}static adagrad(t,e=.1){return new Rh(t,e)}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Es=hk;/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const dk=typeof requestAnimationFrame<"u"?requestAnimationFrame:typeof setImmediate<"u"?setImmediate:n=>n();function fk(){return new Promise(n=>dk(()=>n()))}/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function pk(n,t){const e=n[0].length;n.forEach((r,o)=>{v(r.length===e,()=>`Error in concat${e}D: rank of tensors[${o}] must be the same as the rank of the rest (${e})`)}),v(t>=0&&t<e,()=>`Error in concat${e}D: axis must be between 0 and ${e-1}.`);const s=n[0];n.forEach((r,o)=>{for(let i=0;i<e;i++)v(i===t||r[i]===s[i],()=>`Error in concat${e}D: Shape of tensors[${o}] (${r}) does not match the shape of the rest (${s}) along the non-concatenated axis ${o}.`)})}function vl(n,t){const e=n[0].slice();for(let s=1;s<n.length;s++)e[t]+=n[s][t];return e}/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */var nn;(function(n){n[n.FIRST_DIM_SIZE=0]="FIRST_DIM_SIZE",n[n.VALUE_ROWIDS=1]="VALUE_ROWIDS",n[n.ROW_LENGTHS=2]="ROW_LENGTHS",n[n.ROW_SPLITS=3]="ROW_SPLITS",n[n.ROW_LIMITS=4]="ROW_LIMITS",n[n.ROW_STARTS=5]="ROW_STARTS"})(nn||(nn={}));function mk(n,t,e){let s=new Array;if(e==null&&t==null)return s;if(t==null)for(;s.length<n+e.length;)s.push(-1);else s=t.slice();if(e==null)return s;if(n+e.length!==s.length)throw new Error(`rt input.shape and shape=${t} are incompatible: rt input.rank = ${n+e.length}, but shape.rank = ${s.length}`);for(let r=1;r<e.length;++r){const o=e[r],i=s[s.length-e.length+r],a=s[i];if(o>=0)if(a>=0){if(a!==o)throw new Error(`rt input.shape and shape=${t} are incompatible: rt input.shape[${r+n}] = ${o} but shape[${r+n}] = ${a}`)}else s[i]=o}return s}function gk(n){const t={FIRST_DIM_SIZE:nn.FIRST_DIM_SIZE,VALUE_ROWIDS:nn.VALUE_ROWIDS,ROW_LENGTHS:nn.ROW_LENGTHS,ROW_SPLITS:nn.ROW_SPLITS,ROW_LIMITS:nn.ROW_LIMITS,ROW_STARTS:nn.ROW_STARTS},e=[];for(const s of n)if(s in t)e.push(t[s]);else break;return e}function bk(n){return n.length===0?0:n[0]===nn.FIRST_DIM_SIZE?n.length-1:n.length}function yk(n,t){if(n==null||t==null)return;const e=n.length,s=t.length;if(e>=s)throw new Error(`defaultValue.shape=${n} and ragged tensor flatValues.shape=${t}, are incompatible: defaultValue.rank = ${e} must be less than ragged tensor input flatValues.rank = ${s})`);for(let r=0;r<Math.min(e,s-1);++r){const o=n[r],i=t[r+1];if(o>=0&&i>=0&&o!==1&&o!==i)throw new Error(`defaultValue.shape=${n}, and ragged tensor input flatValues.shape=${t} are incompatible: defaultValue.shape[${r-n.length}] = ${o} but ragged tensor input.flatValues.shape[${r-n.length}] = ${i}`)}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function wk(n,t,e){const s=e*(typeof n=="number"?n:n[0]),r=t*(typeof n=="number"?n:n[1]);return[s,r]}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Hh(n,t,e,s=!0){let r=[];if(s)r=r.concat(t.slice(0)),r.push(n[0]/e),r=r.concat(n.slice(1));else{r=r.concat(n[0]);const o=t.length;for(let i=0;i<o;++i)r=r.concat([n[i+1]/t[i],t[i]]);r=r.concat(n.slice(o+1))}return r}function qh(n,t,e=!0){const s=[];if(e){s.push(t);for(let r=t+1;r<n;++r)r<=2*t?(s.push(r),s.push(r-(t+1))):s.push(r)}else{const r=[],o=[];for(let i=1;i<n;++i)i>=t*2+1||i%2===1?o.push(i):r.push(i);s.push(...r),s.push(0),s.push(...o)}return s}function jh(n,t,e,s=!0){const r=[];s?r.push(n[0]/e):r.push(n[0]*e);for(let o=1;o<n.length;++o)o<=t.length?s?r.push(t[o-1]*n[o]):r.push(n[o]/t[o-1]):r.push(n[o]);return r}function kk(n,t){const e=[0];for(let s=0;s<t;++s)e.push(n[s][0]);return e}function xk(n,t,e){const s=n.slice(0,1);for(let r=0;r<e;++r)s.push(n[r+1]-t[r][0]-t[r][1]);return s}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Kh=1.7580993408473768,Xh=1.0507009873554805;/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Ik=.3275911,Sk=.254829592,vk=-.284496736,Nk=1.421413741,$k=-1.453152027,Tk=1.061405429;/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ds(n,t){if(n.length!==t.length)throw new Error(`Cannot merge real and imag arrays of different lengths. real:${n.length}, imag: ${t.length}.`);const e=new Float32Array(n.length*2);for(let s=0;s<e.length;s+=2)e[s]=n[s/2],e[s+1]=t[s/2];return e}function Ck(n){const t=new Float32Array(n.length/2),e=new Float32Array(n.length/2);for(let s=0;s<n.length;s+=2)t[s/2]=n[s],e[s/2]=n[s+1];return{real:t,imag:e}}function Ak(n){const t=Math.ceil(n.length/4),e=new Float32Array(t),s=new Float32Array(t);for(let r=0;r<n.length;r+=4)e[Math.floor(r/4)]=n[r],s[Math.floor(r/4)]=n[r+1];return{real:e,imag:s}}function Ek(n){const t=Math.floor(n.length/4),e=new Float32Array(t),s=new Float32Array(t);for(let r=2;r<n.length;r+=4)e[Math.floor(r/4)]=n[r],s[Math.floor(r/4)]=n[r+1];return{real:e,imag:s}}function Zh(n,t){const e=n[t*2],s=n[t*2+1];return{real:e,imag:s}}function Dk(n,t,e,s){n[s*2]=t,n[s*2+1]=e}function Fk(n,t){const e=new Float32Array(n/2),s=new Float32Array(n/2);for(let r=0;r<Math.ceil(n/2);r++){const o=(t?2:-2)*Math.PI*(r/n);e[r]=Math.cos(o),s[r]=Math.sin(o)}return{real:e,imag:s}}function Mk(n,t,e){const s=(e?2:-2)*Math.PI*(n/t),r=Math.cos(s),o=Math.sin(s);return{real:r,imag:o}}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Nl="->",Rk=/->/g,Jh=",",Yh="...";function zk(n,t){n=n.replace(/\s/g,"");const e=(n.length-n.replace(Rk,"").length)/Nl.length;if(e<1)throw new Error("Equations without an arrow are not supported.");if(e>1)throw new Error(`Equation must contain exactly one arrow ("${Nl}").`);const[s,r]=n.split(Nl);v(s.indexOf(Yh)===-1,()=>`The ellipsis notation ("${Yh}") is not supported yet.`);const o=s.split(Jh),i=o.length;if(t!==i)throw new Error(`Expected ${i} input tensors, received ${t}`);if(i>2)throw new Error("Support for more than 2 input tensors is not implemented yet.");const a=[];for(let d=0;d<r.length;++d){const f=r[d];if(!o.some(p=>p.indexOf(f)!==-1))throw new Error(`Output subscripts contain the label ${f} not present in the input subscripts.`);a.indexOf(f)===-1&&a.push(f)}for(let d=0;d<s.length;++d){const f=s[d];a.indexOf(f)===-1&&f!==Jh&&a.push(f)}const l=new Array(o.length);for(let d=0;d<i;++d){if(new Set(o[d].split("")).size!==o[d].length)throw new Error(`Found duplicate axes in input component ${o[d]}. Support for duplicate axes in input is not implemented yet.`);l[d]=[];for(let f=0;f<o[d].length;++f)l[d].push(a.indexOf(o[d][f]))}const c=a.length,u=r.length,h=[];for(let d=u;d<c;++d)h.push(d);return{allDims:a,summedDims:h,idDims:l}}function Lk(n,t){let e=new Array(n);e.fill(-1);for(let r=0;r<t.length;++r)e[t[r]]=r;const s=[];for(let r=0;r<n;++r)e[r]===-1&&s.push(r);return e=e.filter(r=>r!==-1),{permutationIndices:e,expandDims:s}}function Ok(n,t,e){const s=new Array(n);for(let r=0;r<e.length;++r){const o=e[r].shape;for(let i=0;i<t[r].length;++i)s[t[r][i]]===void 0?s[t[r][i]]=o[i]:v(s[t[r][i]]===o[i],()=>`Expected dimension ${s[t[r][i]]} at axis ${i} of input shaped ${JSON.stringify(o)}, but got dimension ${o[i]}`)}}function _k(n,t){const e=n,s=[];let r=0;n.length===0&&e.push(-1),r=n.length+1;for(let i=0;i<r;++i)s.push([]);const o=[];for(let i=0;i<e.length;++i){const a=e[i],l=Pk(t,a);for(const c of l)o.indexOf(c)===-1&&(s[i].push(c),o.push(c))}return{path:e,steps:s}}function Bk(n){return n.every((t,e)=>t===e)}function Pk(n,t){const e=[];for(let s=0;s<n.length;++s)(n[s].length===0||n[s].indexOf(t)!==-1||t===-1)&&e.push(s);return e}function Wk(n,t,e=0){let s=[];if(typeof t=="number")v(n.shape[e]%t===0,()=>"Number of splits must evenly divide the axis."),s=new Array(t).fill(n.shape[e]/t);else{const r=t.reduce((i,a)=>(a===-1&&(i+=1),i),0);v(r<=1,()=>"There should be only one negative value in split array.");const o=t.indexOf(-1);if(o!==-1){const i=t.reduce((a,l)=>l>0?a+l:a);t[o]=n.shape[e]-i}v(n.shape[e]===t.reduce((i,a)=>i+a),()=>"The sum of sizes must match the size of the axis dimension."),s=t}return s}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Vk(n){return`Received SparseTensor with denseShape[0] = 0 but
  indices.shape[0] = ${n}`}function Gk(n,t){return`indices(${n}, 0) is invalid: ${t} < 0`}function Uk(n,t,e){return`indices(${n}, 0) is invalid: ${t} >= ${e}`}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Hk(n,t){return`only one output dimension may be -1, not both ${n} and ${t}`}function qk(n,t){return`size ${n} must be non-negative, not ${t}`}function jk(){return"reshape cannot infer the missing input size for an empty tensor unless all specified input sizes are non-zero"}function Kk(n,t){const e=Z(n),s=Z(t);return`Input to reshape is a SparseTensor with ${e}
  dense values, but the requested shape requires a multiple of ${s}. inputShape=${n} outputShape= ${t}`}function Xk(n,t){const e=Z(n),s=Z(t);return`Input to reshape is a tensor with ${e} dense values, but the requested shape has ${s}. inputShape=${n} outputShape=${t}`}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Qh(){return"segment ids must be >= 0"}function Zk(){return"segment ids are not increasing"}function Jk(n,t){return`Segment id ${n} out of range [0, ${t}), possibly because segmentIds input is not sorted.`}function Yk(n,t,e){return`Bad: indices[${n}] == ${t} out of range [0, ${e})`}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Qk(n,t,e,s){const r=t.shape.length,o=n.shape.length;if(s!==0&&(s<-r||s>r))throw new Error(`Expect batchDims in the range of [-${r}, ${r}], but got ${s}`);if(s<0&&(s+=r),s>o)throw new Error(`batchDims (${s}) must be less than rank(x) (
    ${o}).`);if(e<s)throw new Error(`batchDims (${s}) must be less than or equal to axis (${e}).`);for(let h=0;h<s;++h)if(n.shape[h]!==t.shape[h])throw new Error(`x.shape[${h}]: ${n.shape[h]} should be equal to indices.shape[${h}]: ${t.shape[h]}.`);const i=n.shape[e],a=[];let l=1,c=1,u=1;for(let h=0;h<s;++h)a.push(n.shape[h]),l*=n.shape[h];for(let h=s;h<e;h++)a.push(n.shape[h]),c*=n.shape[h];for(let h=s;h<r;h++)a.push(t.shape[h]);for(let h=e+1;h<o;h++)a.push(n.shape[h]),u*=n.shape[h];return{batchSize:l,sliceSize:u,outerSize:c,dimSize:i,outputShape:a}}/**
 * @license
 * Copyright 2018 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function or(n){try{return n.map(t=>Us(t))}catch(t){throw new Error(`Failed to decode encoded string bytes into utf-8, error: ${t}`)}}function tx(n){return n.map(t=>Xn(t))}/**
 * @license
 * Copyright 2017 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */Z1();/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class sn extends Error{constructor(t){super(t),Object.setPrototypeOf(this,sn.prototype)}}class De extends Error{constructor(t){super(t),Object.setPrototypeOf(this,De.prototype)}}class A extends Error{constructor(t){super(t),Object.setPrototypeOf(this,A.prototype)}}class ut extends Error{constructor(t){super(t),Object.setPrototypeOf(this,ut.prototype)}}class $l extends Error{constructor(t){super(t),Object.setPrototypeOf(this,$l.prototype)}}/**
 * @license
 * Copyright 2022 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class td{constructor(t){this.maxEntries=t||100,this.cache=new Map}get(t){let e;return this.cache.has(t)&&(e=this.cache.get(t),this.cache.delete(t),this.cache.set(t,e)),e}put(t,e){if(this.cache.has(t))this.cache.delete(t);else if(this.cache.size>=this.maxEntries){const s=this.cache.keys().next().value;this.cache.delete(s)}this.cache.set(t,e)}getMaxEntries(){return this.maxEntries}setMaxEntries(t){if(t<0)throw new Error(`The maxEntries of LRU caches must be at least 0, but got ${t}.`);if(this.maxEntries>t)for(let e=0;e<this.maxEntries-t;e++){const s=this.cache.keys().next().value;this.cache.delete(s)}this.maxEntries=t}}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function ns(n,t){if(Array.isArray(n)){let e=[];for(let s=0;s<t;s++)e=e.concat(n);return e}else{const e=new Array(t);return e.fill(n),e}}function rn(n,t){if(!n)throw new $l(t)}function ed(n,t){let e=0;for(const s of n)s===t&&e++;return e}function pe(n){return n.length===1?n[0]:n}function xt(n){return Array.isArray(n)?n:[n]}function yn(n){const e=n.replace(/(.)([A-Z][a-z0-9]+)/g,"$1_$2").replace(/([a-z])([A-Z])/g,"$1_$2").toLowerCase();return e[0]!=="_"?e:"private"+e}function ss(n){return n.length<=1||n.indexOf("_")===-1?n:n.replace(/[_]+(\w|$)/g,(t,e)=>e.toUpperCase())}let Fe={};function Tl(n){if(n==null)return null;const t={};return t.className=n.getClassName(),t.config=n.getConfig(),t}function Cl(n){if(!(n==null||typeof n!="object"))if(Array.isArray(n))n.forEach(t=>Cl(t));else{const t=Object.keys(n);for(const e of t){const s=n[e];s!=null&&typeof s=="object"&&(!Array.isArray(s)&&s.type==="ndarray"&&typeof s.value=="number"?n[e]=s.value:Cl(s))}}}function ir(n,t={},e={},s="object",r=!1){if(typeof n=="string"){const o=n;let i;if(o in e)i=e[o];else if(o in Fe)i=Fe[o];else if(i=t[o],i==null)throw new A(`Unknown ${s}: ${n}. This may be due to one of the following reasons:
1. The ${s} is defined in Python, in which case it needs to be ported to TensorFlow.js or your JavaScript code.
2. The custom ${s} is defined in JavaScript, but is not registered properly with tf.serialization.registerClass().`);return i}else{const o=n;if(o.className==null||o.config==null)throw new A(`${s}: Improper config format: ${JSON.stringify(o)}.
'className' and 'config' must set.`);const i=o.className;let a,l;if(i in e?[a,l]=e[i]:i in Fe?[a,l]=Fe.className:i in t&&([a,l]=t[i]),a==null)throw new A(`Unknown ${s}: ${i}. This may be due to one of the following reasons:
1. The ${s} is defined in Python, in which case it needs to be ported to TensorFlow.js or your JavaScript code.
2. The custom ${s} is defined in JavaScript, but is not registered properly with tf.serialization.registerClass().`);if(l!=null){const c={};for(const f of Object.keys(Fe))c[f]=Fe[f];for(const f of Object.keys(e))c[f]=e[f];const u=o.config;u.customObjects=c;const h=Object.assign({},Fe);for(const f of Object.keys(e))Fe[f]=e[f];Cl(o.config);const d=l(a,o.config,e,r);return Fe=Object.assign({},h),d}else{const c=Object.assign({},Fe);for(const h of Object.keys(e))Fe[h]=e[h];const u=new a(o.config);return Fe=Object.assign({},c),u}}}function ex(n,t){return n<t?-1:n>t?1:0}function _o(n,t){return-1*ex(n,t)}function Dn(n){if(n==null)return n;const t=[];for(const e of n)t.indexOf(e)===-1&&t.push(e);return t}function nx(n){if(n==null)throw new A(`Invalid value in obj: ${JSON.stringify(n)}`);for(const t in n)if(n.hasOwnProperty(t))return!1;return!0}function rs(n,t,e){if(e!=null&&n.indexOf(e)<0)throw new A(`${e} is not a valid ${t}.  Valid values are ${n} or null/undefined.`)}function Al(n,t,e=0,s=1/0){return rn(e>=0),rn(s>=e),Array.isArray(n)&&n.length>=e&&n.length<=s&&n.every(r=>typeof r===t)}function Qt(n,t){Array.isArray(n)?(v(n.length>0,()=>`${t} is unexpectedly an empty array.`),n.forEach((e,s)=>Qt(e,`element ${s+1} of ${t}`))):v(Number.isInteger(n)&&n>0,()=>`Expected ${t} to be a positive integer, but got ${nd(n)}.`)}function nd(n){return n===null?"null":Array.isArray(n)?"["+n.map(t=>nd(t)).join(",")+"]":typeof n=="string"?`"${n}"`:`${n}`}function sx(n,t,e){let s=e!=null?e():vn(),r;return(...i)=>{const a=e!=null?e():vn();return a-s<t||(s=a,r=n(...i)),r}}function sd(n){return n==="relu"?"relu":n==="linear"?"linear":n==="elu"?"elu":null}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */let rx=0;function rd(){return rx++}const Bo={};function Po(n=""){return n in Bo||(Bo[n]=0),Bo[n]+=1,n+Bo[n].toString()}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */const ox=["channelsFirst","channelsLast"],ix=["nearest","bilinear"],ax=["valid","same","causal"],lx=["max","avg"],cx=["sum","mul","concat","ave"];/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */const Fs=new Map;function Wt(n){rs(ox,"DataFormat",n)}function ux(n){rs(ix,"InterpolationFormat",n)}function Se(n){rs(ax,"PaddingMode",n)}function od(n){rs(lx,"PoolMode",n)}const ar=[],id="/";function os(n,t){ar.push(n);try{const e=t();return ar.pop(),e}catch(e){throw ar.pop(),e}}function hx(){return ar.length===0?"":ar.join(id)+id}function ad(n){if(!cd(n))throw new Error("Not a valid tensor name: '"+n+"'");return hx()+n}function ld(n){if(!cd(n))throw new Error("Not a valid tensor name: '"+n+"'");Fs.has(n)||Fs.set(n,0);const t=Fs.get(n);if(Fs.set(n,Fs.get(n)+1),t>0){const e=`${n}_${t}`;return Fs.set(e,1),e}else return n}const dx=new RegExp(/^[A-Za-z0-9][-A-Za-z0-9\._\/]*$/);function cd(n){return!!n.match(dx)}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function fx(n){return n===parseInt(n.toString(),10)}function Fn(n,t,e){t==null&&(t=0),e==null&&(e=n.length);let s=1;for(let r=t;r<e;++r)s*=n[r];return s}function Ms(n){if(n.length===0)return Number.NaN;let t=Number.POSITIVE_INFINITY;for(let e=0;e<n.length;e++){const s=n[e];s<t&&(t=s)}return t}function Mn(n){if(n.length===0)return Number.NaN;let t=Number.NEGATIVE_INFINITY;for(let e=0;e<n.length;e++){const s=n[e];s>t&&(t=s)}return t}function Pe(n,t){if(t<n)throw new A(`end (${t}) < begin (${n}) is forbidden.`);const e=[];for(let s=n;s<t;++s)e.push(s);return e}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */let El;function Ht(){return El==null&&(El=Xg().epsilon()),El}function We(){return"channelsLast"}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function on(n,t){return Q(n,t)}function lr(n,t=-1){const e=n.shape.slice();return t<0&&(t=e.length+t+1),e.splice(t,0,1),_(n,e)}function px(n,t){return z(()=>{if(n.shape.length!==2)throw new A(`repeat() expects a rank-2 tensor, but received a rank-${n.shape.length} tensor.`);const e=lr(n,1);return Ml(e,[1,t,1])})}function mx(n){const t=[Fn(n.shape)];return _(n,t)}function gx(n){if(n.rank<=1)throw new A(`batchFlatten requires a minimum rank of 2. Got rank: ${n.rank}.`);const t=[n.shape[0],Fn(n.shape,1)];return _(n,t)}function is(n,t,e){return z(()=>{switch(n.rank){case 1:return gl(n,t,e);case 2:return kh(n,[t,0],[e,n.shape[1]]);case 3:return bl(n,[t,0,0],[e,n.shape[1],n.shape[2]]);case 4:return Ro(n,[t,0,0,0],[e,n.shape[1],n.shape[2],n.shape[3]]);case 5:return Bt(n,[t,0,0,0,0],[e,n.shape[1],n.shape[2],n.shape[3],n.shape[4]]);case 6:return Bt(n,[t,0,0,0,0,0],[e,n.shape[1],n.shape[2],n.shape[3],n.shape[4],n.shape[5]]);default:throw new A(`sliceAlongFirstAxis() received an unsupported tensor rank: ${n.rank}`)}})}function Dl(n,t,e){return z(()=>{switch(n.rank){case 1:return gl(n,t,e);case 2:return kh(n,[0,t],[n.shape[0],e]);case 3:return bl(n,[0,0,t],[n.shape[0],n.shape[1],e]);case 4:return Ro(n,[0,0,0,t],[n.shape[0],n.shape[1],n.shape[2],e]);default:throw new A(`sliceAlongLastAxis() received an unsupported tensor rank: ${n.rank}`)}})}function Wo(n,t,e,s){return z(()=>{switch(n.rank){case 1:return gl(n,t,e);case 2:switch(s){case 1:return is(n,t,e);case 2:return Dl(n,t,e);default:throw new A(`The axis is not within the rank of the tensor ${s}`)}case 3:switch(s){case 1:return is(n,t,e);case 2:return bl(n,[0,t,0],[n.shape[0],e,n.shape[2]]);case 3:return Dl(n,t,e);default:throw new A(`The axis is not within the rank of the tensor ${s}`)}case 4:switch(s){case 1:return is(n,t,e);case 2:return Ro(n,[0,t,0,0],[n.shape[0],e,n.shape[2],n.shape[3]]);case 3:return Ro(n,[0,0,t,0],[n.shape[0],n.shape[1],e,n.shape[3]]);case 4:return Dl(n,t,e);default:throw new A(`The axis is not within the rank of the tensor ${s}`)}default:throw new A(`sliceAlongLastAxis() received an unsupported tensor rank: ${n.rank}`)}})}function Fl(n,t=-1){let e;return t<0&&(e=n[0].rank,e!==0?t=e:t=0),t===n[0].rank&&(t=-1),_e(n,t)}function ud(n,t){switch(n.rank){case 1:return py([n,t]);case 2:return gy([n,t],0);case 3:return yy([n,t],0);case 4:return ky([n,t],0);default:throw new A(`concatAlongFirstAxis() received an unsupported tensor rank: ${n.rank}`)}}function Ml(n,t){if(Array.isArray(t)||(t=[t]),n.rank!==t.length)throw new A(`The length of input n (${t.length}) does not match the number of dimensions in input x (${n.rank})`);return tn(n,t)}function Vo(n,t=0,e=1,s,r){return uw(n,t,e,s,r)}function an(n,t,e,s){if(n.rank<2||t.rank<2)throw new ut(`dot requires both inputs to be rank >= 2 but got x shape = ${n.shape} and y shape = ${t.shape}`);if(t.rank>=3){const r=n.shape.slice(-1)[0],o=t.shape.slice(-2)[0];if(r!==o)throw new ut(`If rank y >= 3, then the second last dim of y must equal the last dim of x but got x shape = ${n.shape} and  y shape = ${t.shape}`)}if(n.rank===2&&t.rank===2)return Th({a:n,b:t,transposeA:!1,transposeB:!1,bias:s?Rl(n.rank,s,We()):null,activation:e});{const r=n.shape.slice(),o=r.pop();n=_(n,[-1,o]);const i=t.shape.slice(),a=i.pop(),l=i.pop(),c=[...i,a],u=Array.from({length:t.rank},(p,g)=>g===0?t.rank-2:g<=t.rank-2?g-1:g);t=_(bt(t,u),[l,-1]);const h=[...r,...c];return _(Th({a:n,b:t,transposeA:!1,transposeB:!1,bias:s?Rl(n.rank,s,We()):null,activation:e}),h)}}function hd(n,t,e){return z(()=>(Array.isArray(t)?t=ke(t,"int32"):t=Q(t,"int32"),ah(n,t,e)))}function cr(n){return D(n,n)}function Rl(n,t,e){const s=t.shape;if(t.rank!==1&&t.rank!==n)throw new A(`Unexpected bias dimensions: ${t.rank}; expected it to be 1 or ${n}`);if(n===5){if(e==="channelsFirst")return s.length===1?_(t,[1,s[0],1,1,1]):_(t,[1,s[3],s[0],s[1],s[2]]);if(e==="channelsLast")return s.length===1?_(t,[1,1,1,1,s[0]]):_(t,[1].concat(s))}else if(n===4){if(e==="channelsFirst")return s.length===1?_(t,[1,s[0],1,1]):_(t,[1,s[2],s[0],s[1]]);if(e==="channelsLast")return s.length===1?_(t,[1,1,1,s[0]]):_(t,[1].concat(s))}else if(n===3){if(e==="channelsFirst")return s.length===1?_(t,[1,s[0],1]):_(t,[1,s[1],s[0]]);if(e==="channelsLast")return s.length===1?_(t,[1,1,s[0]]):_(t,[1].concat(s))}else if(n<3)return t;throw new A(`Unsupported input rank by biasAdd: ${t.rank}`)}function Ve(n,t,e){return z(()=>(e==null&&(e=We()),Wt(e),X(n,Rl(n.rank,t,e))))}function bx(n,t=1){if(t!==1)throw new ut(`Support for alpha values other than 1 (${t}) is not implemented yet.`);return al(n)}function yx(n){return z(()=>rt(n,X(fe(n),1)))}function dd(n,t,e,s){return z(()=>Kw(n,t,e,s))}function wx(n){return z(()=>{const t=X(.5,D(.2,n));return $e(t,0,1)})}function ur(n,t,e=!1){return e?n():t()}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */const kx=["fanIn","fanOut","fanAvg"],xx=["normal","uniform","truncatedNormal"];/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Ix(n){rs(kx,"FanMode",n)}function Sx(n){rs(xx,"Distribution",n)}class Me extends As{fromConfigUsesCustomObjects(){return!1}getConfig(){return{}}}class fd extends Me{apply(t,e){return ae(t,e)}}fd.className="Zeros",H(fd);class zl extends Me{apply(t,e){return Cn(t,e)}}zl.className="Ones",H(zl);class pd extends Me{constructor(t){if(super(),typeof t!="object")throw new A(`Expected argument of type ConstantConfig but got ${t}`);if(t.value===void 0)throw new A(`config must have value set but got ${t}`);this.value=t.value}apply(t,e){return z(()=>D(kt(this.value),Cn(t,e)))}getConfig(){return{value:this.value}}}pd.className="Constant",H(pd);class md extends Me{constructor(t){super(),this.DEFAULT_MINVAL=-.05,this.DEFAULT_MAXVAL=.05,this.minval=t.minval||this.DEFAULT_MINVAL,this.maxval=t.maxval||this.DEFAULT_MAXVAL,this.seed=t.seed}apply(t,e){return sr(t,this.minval,this.maxval,e,this.seed)}getConfig(){return{minval:this.minval,maxval:this.maxval,seed:this.seed}}}md.className="RandomUniform",H(md);class gd extends Me{constructor(t){super(),this.DEFAULT_MEAN=0,this.DEFAULT_STDDEV=.05,this.mean=t.mean||this.DEFAULT_MEAN,this.stddev=t.stddev||this.DEFAULT_STDDEV,this.seed=t.seed}apply(t,e){if(e=e||"float32",e!=="float32"&&e!=="int32")throw new ut(`randomNormal does not support dType ${e}.`);return Vo(t,this.mean,this.stddev,e,this.seed)}getConfig(){return{mean:this.mean,stddev:this.stddev,seed:this.seed}}}gd.className="RandomNormal",H(gd);class bd extends Me{constructor(t){super(),this.DEFAULT_MEAN=0,this.DEFAULT_STDDEV=.05,this.mean=t.mean||this.DEFAULT_MEAN,this.stddev=t.stddev||this.DEFAULT_STDDEV,this.seed=t.seed}apply(t,e){if(e=e||"float32",e!=="float32"&&e!=="int32")throw new ut(`truncatedNormal does not support dType ${e}.`);return Ih(t,this.mean,this.stddev,e,this.seed)}getConfig(){return{mean:this.mean,stddev:this.stddev,seed:this.seed}}}bd.className="TruncatedNormal",H(bd);class yd extends Me{constructor(t){super(),this.gain=t.gain!=null?t.gain:1}apply(t,e){return z(()=>{if(t.length!==2||t[0]!==t[1])throw new A("Identity matrix initializer can only be used for 2D square matrices.");return D(this.gain,ih(t[0]))})}getConfig(){return{gain:this.gain}}}yd.className="Identity",H(yd);function vx(n,t="channelsLast"){let e,s;if(Wt(t),n.length===2)e=n[0],s=n[1];else if([3,4,5].indexOf(n.length)!==-1){if(t==="channelsFirst"){const r=Fn(n,2);e=n[1]*r,s=n[0]*r}else if(t==="channelsLast"){const r=Fn(n,0,n.length-2);e=n[n.length-2]*r,s=n[n.length-1]*r}}else{const r=Fn(n);e=Math.sqrt(r),s=Math.sqrt(r)}return[e,s]}class xe extends Me{constructor(t){if(super(),t.scale<0)throw new A(`scale must be a positive float. Got: ${t.scale}`);this.scale=t.scale==null?1:t.scale,this.mode=t.mode==null?"fanIn":t.mode,Ix(this.mode),this.distribution=t.distribution==null?"normal":t.distribution,Sx(this.distribution),this.seed=t.seed}apply(t,e){const s=vx(t),r=s[0],o=s[1];let i=this.scale;if(this.mode==="fanIn"?i/=Math.max(1,r):this.mode==="fanOut"?i/=Math.max(1,o):i/=Math.max(1,(r+o)/2),this.distribution==="normal"){const a=Math.sqrt(i);if(e=e||"float32",e!=="float32"&&e!=="int32")throw new ut(`${this.getClassName()} does not support dType ${e}.`);return Ih(t,0,a,e,this.seed)}else{const a=Math.sqrt(3*i);return sr(t,-a,a,e,this.seed)}}getConfig(){return{scale:this.scale,mode:this.mode,distribution:this.distribution,seed:this.seed}}}xe.className="VarianceScaling",H(xe);class Ll extends xe{constructor(t){super({scale:1,mode:"fanAvg",distribution:"uniform",seed:t==null?null:t.seed})}getClassName(){return xe.className}}Ll.className="GlorotUniform",H(Ll);class Ol extends xe{constructor(t){super({scale:1,mode:"fanAvg",distribution:"normal",seed:t==null?null:t.seed})}getClassName(){return xe.className}}Ol.className="GlorotNormal",H(Ol);class _l extends xe{constructor(t){super({scale:2,mode:"fanIn",distribution:"normal",seed:t==null?null:t.seed})}getClassName(){return xe.className}}_l.className="HeNormal",H(_l);class Bl extends xe{constructor(t){super({scale:2,mode:"fanIn",distribution:"uniform",seed:t==null?null:t.seed})}getClassName(){return xe.className}}Bl.className="HeUniform",H(Bl);class Pl extends xe{constructor(t){super({scale:1,mode:"fanIn",distribution:"normal",seed:t==null?null:t.seed})}getClassName(){return xe.className}}Pl.className="LeCunNormal",H(Pl);class Wl extends xe{constructor(t){super({scale:1,mode:"fanIn",distribution:"uniform",seed:t==null?null:t.seed})}getClassName(){return xe.className}}Wl.className="LeCunUniform",H(Wl);class wd extends Me{constructor(t){super(),this.DEFAULT_GAIN=1,this.ELEMENTS_WARN_SLOW=2e3,this.gain=t.gain==null?this.DEFAULT_GAIN:t.gain,this.seed=t.seed}apply(t,e){return z(()=>{if(t.length<2)throw new ut("Shape must be at least 2D.");if(e!=="int32"&&e!=="float32"&&e!==void 0)throw new TypeError(`Unsupported data type ${e}.`);e=e;const s=Z(t.slice(0,-1)),r=t[t.length-1],o=s*r;o>this.ELEMENTS_WARN_SLOW&&console.warn(`Orthogonal initializer is being called on a matrix with more than ${this.ELEMENTS_WARN_SLOW} (${o}) elements: Slowness may result.`);const i=[Math.max(r,s),Math.min(r,s)],a=Vo(i,0,1,e,this.seed),l=q1.qr(a,!1);let c=l[0];const h=l[1].flatten().stridedSlice([0],[Math.min(r,s)*Math.min(r,s)],[Math.min(r,s)+1]);return c=D(c,h.sign()),s<r&&(c=c.transpose()),D(kt(this.gain),c.reshape(t))})}getConfig(){return{gain:this.gain,seed:this.seed}}}wd.className="Orthogonal",H(wd);const kd={constant:"Constant",glorotNormal:"GlorotNormal",glorotUniform:"GlorotUniform",heNormal:"HeNormal",heUniform:"HeUniform",identity:"Identity",leCunNormal:"LeCunNormal",leCunUniform:"LeCunUniform",ones:"Ones",orthogonal:"Orthogonal",randomNormal:"RandomNormal",randomUniform:"RandomUniform",truncatedNormal:"TruncatedNormal",varianceScaling:"VarianceScaling",zeros:"Zeros"};function xd(n,t={}){return ir(n,Ee.getMap().classNameMap,t,"initializer")}function Ot(n){return Tl(n)}function Rt(n){if(typeof n=="string"){const t=n in kd?kd[n]:n;if(t==="GlorotNormal")return new Ol;if(t==="GlorotUniform")return new Ll;if(t==="HeNormal")return new _l;if(t==="HeUniform")return new Bl;if(t==="LeCunNormal")return new Pl;if(t==="LeCunUniform")return new Wl;{const e={};return e.className=t,e.config={},xd(e)}}else return n instanceof Me?n:xd(n)}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Vl(n){return Array.isArray(n)&&Array.isArray(n[0])}function Go(n){return n.length===0?[]:Array.isArray(n[0])?n:[n]}function ct(n){let t;if(Array.isArray(n)){if(n.length!==1)throw new A(`Expected Tensor length to be 1; got ${n.length}`);t=n[0]}else t=n;return t}function yt(n){if(Array.isArray(n)&&Array.isArray(n[0])){if(n.length===1)return n=n,n[0];throw new A(`Expected exactly 1 Shape; got ${n.length}`)}else return n}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Uo(n){let t=0;for(const e of n)e.shape.length===0?t+=1:t+=e.shape.reduce((s,r)=>s*r);return t}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */const Id="Variable";class Nx{constructor(t,e="float32",s=Id,r=!0,o=null){this.dtype=e??"float32",this.shape=t.shape,this.id=rd(),s=s??Id,this.originalName=ad(s),this.name=ld(this.originalName),this.trainable_=r,this.constraint=o,this.val=Gw(t,this.trainable_,this.name,this.dtype)}read(){return this.assertNotDisposed(),this.val}write(t){return this.assertNotDisposed(),$x(this.val,t),this.val.id!==t.id&&(this.val.assign(t),this.constraint!=null&&this.val.assign(this.constraint.apply(this.val))),this}dispose(){this.assertNotDisposed(),this.val.dispose()}assertNotDisposed(){if(this.val.isDisposed)throw new Error(`LayersVariable ${this.name} is already disposed.`)}get trainable(){return this.trainable_}set trainable(t){this.trainable_=t,this.val.trainable=t}}function $x(n,t){if(n.shape.toString()!==t.shape.toString())throw new Error("Shape mismatch: "+JSON.stringify(n.shape)+" vs. "+JSON.stringify(t.shape))}function Gl(n){return n.map(t=>t.read())}function Ul(n){n.forEach(t=>{t[0].write(t[1])})}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class qt{constructor(t){this.dtype=t.dtype,this.shape=t.shape,t.shape!=null?this.ndim=t.shape.length:this.ndim=t.ndim,this.maxNDim=t.maxNDim,this.minNDim=t.minNDim,this.axes=t.axes||{}}}class ln{constructor(t,e,s,r,o,i,a){this.dtype=t,this.shape=e,this.sourceLayer=s,this.inputs=r,this.callArgs=o,this.outputTensorIndex=a,this.id=rd(),i!=null&&(this.originalName=ad(i),this.name=ld(this.originalName)),this.rank=e.length}}let Tx=0;class Ho{constructor(t,e){this.callArgs=e,this.id=Tx++,this.outboundLayer=t.outboundLayer,this.inboundLayers=t.inboundLayers,this.nodeIndices=t.nodeIndices,this.tensorIndices=t.tensorIndices,this.inputTensors=t.inputTensors,this.outputTensors=t.outputTensors,this.inputMasks=t.inputMasks,this.outputMasks=t.outputMasks,this.inputShapes=t.inputShapes,this.outputShapes=t.outputShapes;for(const s of t.inboundLayers)s!=null&&s.outboundNodes.push(this);t.outboundLayer.inboundNodes.push(this)}getConfig(){const t=[];for(const e of this.inboundLayers)e!=null?t.push(e.name):t.push(null);return{outboundLayer:this.outboundLayer?this.outboundLayer.name:null,inboundLayers:t,nodeIndices:this.nodeIndices,tensorIndices:this.tensorIndices}}}let Cx=0;class pt extends As{constructor(t={}){super(),this._callHook=null,this._addedWeightNames=[],this._stateful=!1,this.id=Cx++,this.activityRegularizer=null,this.inputSpec=null,this.supportsMasking=!1,this._trainableWeights=[],this._nonTrainableWeights=[],this._losses=[],this._updates=[],this._built=!1,this.inboundNodes=[],this.outboundNodes=[];let e=t.name;if(!e){const s=this.getClassName();e=yn(s)+"_"+Po(s)}if(this.name=e,this.trainable_=t.trainable==null?!0:t.trainable,t.inputShape!=null||t.batchInputShape!=null){let s;if(t.batchInputShape!=null)s=t.batchInputShape;else if(t.inputShape!=null){let o=null;t.batchSize!=null&&(o=t.batchSize),s=[o].concat(t.inputShape)}this.batchInputShape=s;let r=t.dtype;r==null&&(r=t.inputDType),r==null&&(r="float32"),this.dtype=r}t.weights!=null?this.initialWeights=t.weights:this.initialWeights=null,this._refCount=null,this.fastWeightInitDuringBuild=!1}static nodeKey(t,e){return t.name+"_ib-"+e.toString()}getNodeAtIndex(t,e){if(this.inboundNodes.length===0)throw new De(`The layer has never been called and thus has no defined ${e}.`);if(this.inboundNodes.length<=t)throw new A(`Asked to get ${e} at node ${t}, but the layer has only ${this.inboundNodes.length} inbound nodes.`);return this.inboundNodes[t]}getInputAt(t){return pe(this.getNodeAtIndex(t,"input").inputTensors)}getOutputAt(t){return pe(this.getNodeAtIndex(t,"output").outputTensors)}get input(){if(this.inboundNodes.length>1)throw new sn(`Layer ${this.name} has multiple inbound nodes, hence the notion of "layer input" is ill-defined. Use \`getInputAt(nodeIndex)\` instead.`);if(this.inboundNodes.length===0)throw new sn(`Layer ${this.name} is not connected, no input to return.`);return pe(this.getNodeAtIndex(0,"input").inputTensors)}get output(){if(this.inboundNodes.length===0)throw new sn(`Layer ${this.name} has no inbound nodes.`);if(this.inboundNodes.length>1)throw new sn(`Layer ${this.name} has multiple inbound nodes, hence the notion of "layer output" is ill-defined. Use \`getOutputAt(nodeIndex)\` instead.`);return pe(this.getNodeAtIndex(0,"output").outputTensors)}get losses(){return this._losses}calculateLosses(){return this.losses.map(t=>t())}get updates(){return this._updates}get built(){return this._built}set built(t){this._built=t}get trainable(){return this.trainable_}set trainable(t){this._trainableWeights.forEach(e=>e.trainable=t),this.trainable_=t}get trainableWeights(){return this.trainable_?this._trainableWeights.filter(t=>t.trainable):[]}set trainableWeights(t){this._trainableWeights=t}get nonTrainableWeights(){return this.trainable?this._trainableWeights.filter(t=>!t.trainable).concat(this._nonTrainableWeights):this._trainableWeights.concat(this._nonTrainableWeights)}set nonTrainableWeights(t){this._nonTrainableWeights=t}get weights(){return this.trainableWeights.concat(this.nonTrainableWeights)}get stateful(){return this._stateful}resetStates(){if(!this.stateful)throw new Error("Cannot call the resetStates() method of a non-stateful Layer object.")}assertInputCompatibility(t){const e=xt(t);if(this.inputSpec==null||this.inputSpec.length===0)return;const s=xt(this.inputSpec);if(e.length!==s.length)throw new A(`Layer ${this.name} expects ${s.length} inputs, but it received ${e.length} input tensors. Input received: ${t}`);for(let r=0;r<e.length;r++){const o=e[r],i=s[r];if(i==null)continue;const a=o.rank;if(i.ndim!=null&&a!==i.ndim)throw new A(`Input ${r} is incompatible with layer ${this.name}: expected ndim=${i.ndim}, found ndim=${a}`);if(i.maxNDim!=null&&a>i.maxNDim)throw new A(`Input ${r} is incompatible with layer ${this.name}: expected max_ndim=${i.maxNDim}, found ndim=${a}`);if(i.minNDim!=null&&a<i.minNDim)throw new A(`Input ${r} is incompatible with layer ${this.name}: expected min_ndim=${i.minNDim}, found ndim=${a}.`);if(i.dtype!=null&&o.dtype!==i.dtype)throw new A(`Input ${r} is incompatible with layer ${this.name} : expected dtype=${i.dtype}, found dtype=${o.dtype}.`);if(i.axes){const l=o.shape;for(const c in i.axes){const u=Number(c),h=i.axes[c],d=u>=0?l[u]:l[l.length+u];if(h!=null&&[h,null].indexOf(d)===-1)throw new A(`Input ${r} is incompatible with layer ${this.name}: expected axis ${u} of input shape to have value ${h} but got shape ${l}.`)}}if(i.shape!=null)for(let l=0;l<i.shape.length;++l){const c=i.shape[l],u=o.shape[l];if(c!=null&&u!=null&&c!==u)throw new A(`Input ${r} is incompatible with layer ${this.name}: expected shape=${i.shape}, found shape=${o.shape}.`)}}}call(t,e){return t}invokeCallHook(t,e){this._callHook!=null&&this._callHook(t,e)}setCallHook(t){this._callHook=t}clearCallHook(){this._callHook=null}apply(t,e){e=e||{},this.assertNotDisposed();const s=xt(t),r=Dx(t),o=Fx(t);if(r===o)throw new A("Arguments to apply() must be all SymbolicTensors or all Tensors");return os(this.name,()=>{if(!this.built){this.assertInputCompatibility(t);const i=[];for(const a of xt(t))i.push(a.shape);this.build(pe(i)),this.built=!0,this.initialWeights&&this.setWeights(this.initialWeights),this._refCount===null&&o&&(this._refCount=1)}if(this.assertInputCompatibility(t),o){let i=this.call(t,e);this.supportsMasking&&this.setMaskMetadata(t,i);const a=xt(i),l=[];for(let c of a)s.indexOf(c)!==-1&&(c=c.clone()),l.push(c);if(i=pe(l),this.activityRegularizer!=null)throw new ut("Layer invocation in the presence of activity regularizer(s) is not supported yet.");return i}else{const i=Ax(t),a=this.computeOutputShape(i);let l;const c=Ex(t);if(this.warnOnIncompatibleInputShape(Array.isArray(t)?i[0]:i),a!=null&&a.length>0&&Array.isArray(a[0])?l=a.map((u,h)=>new ln(c,u,this,xt(t),e,this.name,h)):l=new ln(c,a,this,xt(t),e,this.name),this.addInboundNode(t,l,null,null,i,a,e),this._refCount++,this.activityRegularizer!=null)throw new ut("Layer invocation in the presence of activity regularizer(s) is not supported yet.");return l}})}warnOnIncompatibleInputShape(t){if(this.batchInputShape!=null)if(t.length!==this.batchInputShape.length)console.warn(`The rank of the input tensor provided (shape: ${JSON.stringify(t)}) does not match that of the batchInputShape (${JSON.stringify(this.batchInputShape)}) of the layer ${this.name}`);else{let e=!1;this.batchInputShape.forEach((s,r)=>{s!=null&&t[r]!=null&&t[r]!==s&&(e=!0)}),e&&console.warn(`The shape of the input tensor (${JSON.stringify(t)}) does not match the expectation of layer ${this.name}: ${JSON.stringify(this.batchInputShape)}`)}}get outputShape(){if(this.inboundNodes==null||this.inboundNodes.length===0)throw new sn(`The layer ${this.name} has never been called and thus has no defined output shape.`);const t=[];for(const e of this.inboundNodes){const s=JSON.stringify(e.outputShapes);t.indexOf(s)===-1&&t.push(s)}if(t.length===1){const e=this.inboundNodes[0].outputShapes;return Array.isArray(e)&&Array.isArray(e[0])&&e.length===1?e[0]:e}else throw new sn(`The layer ${this.name} has multiple inbound nodes with different output shapes. Hence the notion of "output shape" is ill-defined for the layer.`)}countParams(){if(!this.built)throw new De(`You tried to call countParams() on ${this.name}, but the layer is not built yet. Build it first by calling build(batchInputShape).`);return Uo(this.weights)}build(t){this.built=!0}getWeights(t=!1){return Gl(t?this.trainableWeights:this.weights)}setWeights(t){z(()=>{const e=this.weights;if(e.length!==t.length)throw new A(`You called setWeights(weights) on layer "${this.name}" with a weight list of length ${t.length}, but the layer was expecting ${e.length} weights. Provided weights: ${t}...`);if(e.length===0)return;const s=[],r=Gl(e);for(let o=0;o<r.length;++o){const i=r[o],a=e[o],l=t[o];if(!oe(i.shape,l.shape))throw new A(`Layer weight shape ${i.shape} not compatible with provided weight shape ${l.shape}`);s.push([a,l])}Ul(s)})}addWeight(t,e,s,r,o,i,a,l){if(this._addedWeightNames.indexOf(t)!==-1)throw new A(`Duplicate weight name ${t} for layer ${this.name}`);this._addedWeightNames.push(t),s==null&&(s="float32"),this.fastWeightInitDuringBuild&&(r=l!=null?l():Rt("zeros"));const c=r.apply(e,s),u=new Nx(c,s,t,i,a);return c.dispose(),o!=null&&this.addLoss(()=>o.apply(u.read())),i==null&&(i=!0),i?this._trainableWeights.push(u):this._nonTrainableWeights.push(u),u}setFastWeightInitDuringBuild(t){this.fastWeightInitDuringBuild=t}addLoss(t){t==null||Array.isArray(t)&&t.length===0||(t=xt(t),this._losses!==void 0&&this._losses!==null&&this.losses.push(...t))}computeOutputShape(t){return t}computeMask(t,e){if(!this.supportsMasking){if(e!=null)if(Array.isArray(e))e.forEach(s=>{if(s!=null)throw new TypeError(`Layer ${this.name} does not support masking, but was passed an inputMask.`)});else throw new TypeError(`Layer ${this.name} does not support masking, but was passed an inputMask.`);return null}return e}setMaskMetadata(t,e,s){if(!this.supportsMasking)return;const r=this.computeMask(t,s),o=xt(e),i=xt(r);if(o.length!==i.length)throw new Error(`${this.name} outputs ${o.length} tensors but ${o.length} masks for those tensors`);for(let a=0;a<o.length;a++)o[a].kerasMask=i[a]}addInboundNode(t,e,s,r,o,i,a=null){const l=xt(t);e=xt(e),s=xt(s),r=xt(r),o=Go(o),i=Go(i);const c=[],u=[],h=[];for(const d of l)c.push(d.sourceLayer),u.push(d.nodeIndex),h.push(d.tensorIndex);new Ho({outboundLayer:this,inboundLayers:c,nodeIndices:u,tensorIndices:h,inputTensors:l,outputTensors:e,inputMasks:s,outputMasks:r,inputShapes:o,outputShapes:i},a);for(let d=0;d<e.length;d++)e[d].sourceLayer=this,e[d].nodeIndex=this.inboundNodes.length-1,e[d].tensorIndex=d}getConfig(){const t={name:this.name,trainable:this.trainable};return this.batchInputShape!=null&&(t.batchInputShape=this.batchInputShape),this.dtype!=null&&(t.dtype=this.dtype),t}disposeWeights(){return this.weights.forEach(t=>t.dispose()),this.weights.length}assertNotDisposed(){if(this._refCount===0)throw new Error(`Layer '${this.name}' is already disposed.`)}dispose(){if(!this.built)throw new Error(`Cannot dispose Layer ${this.name} because it has not been built yet.`);if(this._refCount===null)throw new Error(`Cannot dispose Layer ${this.name} because it has not been used yet.`);this.assertNotDisposed();let t=0;return--this._refCount===0&&(t=this.disposeWeights()),{refCountAfterDispose:this._refCount,numDisposedVariables:t}}}function Ax(n){n=xt(n);const t=[];for(const e of n)t.push(e.shape);return pe(t)}function Ex(n){return"float32"}function Sd(n,t,e){if((t==null||e!=null&&e>0)&&(t=n.sourceLayer,e=n.nodeIndex),t.inboundNodes.length===0)return[n];{const s=t.inboundNodes[e];if(s.inboundLayers.length===0)return s.inputTensors;{const r=[];for(let o=0;o<s.inboundLayers.length;o++){const i=s.inputTensors[o],a=s.inboundLayers[o],l=s.nodeIndices[o],c=Sd(i,a,l);for(const u of c)r.indexOf(u)===-1&&r.push(u)}return r}}}function Dx(n){let t=!0;for(const e of xt(n))if(!(e instanceof ln)){t=!1;break}return t}function Fx(n){let t=!0;for(const e of xt(n))if(e instanceof ln){t=!1;break}return t}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class hr extends pt{constructor(t){if(super({dtype:t.dtype,name:t.name!=null?t.name:Po("input").toString()}),t.batchSize==null&&(t.batchSize=null),t.sparse==null&&(t.sparse=!1),this.trainable=!1,this.built=!0,this.sparse=t.sparse,t.inputShape!=null&&t.batchInputShape!=null)throw new A("Only provide the inputShape OR batchInputShape argument to inputLayer, not both at the same time.");let e=t.batchInputShape;if(e==null){if(t.inputShape==null)throw new A("An InputLayer should be passed either a `batchInputShape` or an `inputShape`.");e=[t.batchSize].concat(t.inputShape)}else if(t.batchSize!=null)throw new A("Cannot specify batchSize if batchInputShape is specified when creating an InputLayer.");const s=t.dtype||"float32";this.batchInputShape=e,this.dtype=s,this.inputSpec=[{shape:e}];const r=new ln(this.dtype,this.batchInputShape,this,[],{},this.name);r.nodeIndex=0,r.tensorIndex=0,new Ho({outboundLayer:this,inboundLayers:[],nodeIndices:[],tensorIndices:[],inputTensors:[r],outputTensors:[r],inputMasks:[null],outputMasks:[null],inputShapes:[e],outputShapes:[e]})}apply(t,e){throw new A(`Cannot pass any input to an InputLayer's apply() method. InputLayer name: ${this.name}`)}dispose(){return{refCountAfterDispose:this._refCount,numDisposedVariables:0}}getConfig(){return{batchInputShape:this.batchInputShape,dtype:this.dtype,sparse:this.sparse,name:this.name}}}hr.className="InputLayer",H(hr);function Mx(n){if(n.batchShape==null&&n.shape==null)throw new Error("Please provide to Input either a `shape` or a `batchShape` argument. Note that `shape` does not include the batch dimension.");if(n.batchShape!=null&&n.shape!=null)throw new A("Please provide either a `shape` or `batchShape` argument to Input, but not both.");let t=n.batchShape;n.shape!=null&&t==null&&(t=[null].concat(n.shape));let e=n.dtype;return e==null&&(e="float32"),new hr({batchInputShape:t,name:n.name,dtype:e,sparse:n.sparse}).inboundNodes[0].outputTensors[0]}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Rx(n,t){if(n.dtype==null||n.dtype===t.dtype)return t;try{return Q(t,n.dtype)}catch{throw new A(`The dtype of the feed (${t.dtype}) can not be cast to the dtype of the key '${n.name}' (${n.dtype}).`)}}class Rn{constructor(t){if(this.id2Value={},this.id2Mask={},this.name2Id={},t instanceof Rn)for(const e in t.id2Value)this.id2Value[e]=t.id2Value[e],e in t.id2Mask&&(this.id2Mask[e]=t.id2Mask[e]);else{if(t==null)return;for(const e of t)this.add(e.key,e.value)}}add(t,e,s){if(this.id2Value[t.id]==null)this.id2Value[t.id]=Rx(t,e),this.name2Id[t.name]=t.id,s!=null&&(this.id2Mask[t.id]=s);else throw new A(`Duplicate key: name=${t.name}, id=${t.id}`);return this}addFeed(t){this.add(t.key,t.value)}hasKey(t){return this.id2Value[t.id]!=null}names(){return Object.keys(this.name2Id)}getValue(t){if(t instanceof ln){if(this.id2Value[t.id]==null)throw new A(`Nonexistent key: ${t.name}`);return this.id2Value[t.id]}else{const e=this.name2Id[t];if(e==null)throw new A(`Feed dict has no SymbolicTensor name: ${t}`);return this.id2Value[e]}}getMask(t){if(t instanceof ln){if(this.id2Value[t.id]==null)throw new A(`Nonexistent key: ${t.name}`);return this.id2Mask[t.id]}else{const e=this.name2Id[t];if(e==null)throw new A(`Feed dict has no SymbolicTensor name: ${t}`);return this.id2Mask[e]}}disposeMasks(){this.id2Mask!=null&&dt(this.id2Mask)}}const qo=new td,jo=new td;function zx(n){qo!=null&&qo.setMaxEntries(n),jo!=null&&jo.setMaxEntries(n)}function dr(n,t,e,s){const r=e==null?!1:e.training,o=Array.isArray(n),i=o?n:[n],a=i.map(p=>p.name),l=[],c=t.names();for(const p of a)c.indexOf(p)!==-1?l.push(t.getValue(p)):l.push(null);const u=a.join(",")+"|"+t.names().sort().join(",");let h=qo.get(u),d;if(h==null){const p=Lx(i,t);h=p.sorted,d=p.recipientCounts,qo.put(u,h),jo.put(u,d)}d={},r||Object.assign(d,jo.get(u));const f=new Rn(t);for(let p=0;p<h.length;++p){const g=h[p],m=g.sourceLayer;if(m instanceof hr)continue;const b=[],y=[],k=[];let w=!1;for(const N of g.inputs){const $=f.getValue(N),x=f.getMask(N);b.push($),y.push(x),x!=null&&(w=!0),r||(d[N.name]--,d[N.name]===0&&!t.hasKey(N)&&a.indexOf(N.name)===-1&&!$.isDisposed&&N.sourceLayer.stateful!==!0&&k.push($))}w&&(e=e||{},e.mask=y[0]);const I=xt(m.apply(b,e));let S=null;m.supportsMasking&&(S=m.computeMask(b,y));const T=_x(g),C=Array.isArray(T)?T:[T];for(let N=0;N<C.length;++N){f.hasKey(C[N])||f.add(C[N],I[N],Array.isArray(S)?S[0]:S);const $=a.indexOf(C[N].name);$!==-1&&(l[$]=I[N])}r||dt(k)}return f.disposeMasks(),o?l:l[0]}function Lx(n,t){v(n!=null&&n.length>0,()=>"Expected at least one fetch, got none");let e=[],s={};if(n.length===1){const r=vd(n[0],t);e=r.sorted,s=r.recipientMap}else{const r=new Set;for(const o of n){const{sorted:i,recipientMap:a}=vd(o,t);for(const l of i)r.has(l.name)||(e.push(l),r.add(l.name));for(const l in a)s[l]==null&&(s[l]=new Set),a[l].forEach(c=>s[l].add(c))}}return{sorted:e,recipientCounts:Ox(s)}}function Ox(n){const t={};for(const e in n)t[e]=n[e].size;return t}function vd(n,t){const e=new Set,s=[],r={};for(const a of t.names())e.add(a);const o=[],i=[];for(o.push(n);o.length>0;){const a=o[o.length-1];if(e.has(a.name)){o.pop();continue}const l=i[i.length-1]===o.length-1;if(a.inputs.length===0||l)o.pop(),s.push(a),e.add(a.name),l&&i.pop();else{i.push(o.length-1);for(const c of a.inputs)r[c.name]==null&&(r[c.name]=new Set),r[c.name].add(a.name),!e.has(c.name)&&o.push(c)}}return{sorted:s,recipientMap:r}}function _x(n){let t;if(n.sourceLayer.inboundNodes.length===1)t=n.sourceLayer.output;else{let e=null;for(let s=0;s<n.sourceLayer.inboundNodes.length;++s)for(const r of n.sourceLayer.inboundNodes[s].outputTensors)if(r.id===n.id){e=s;break}t=n.sourceLayer.getOutputAt(e)}return t}/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */gt().registerFlag("TOPOLOGICAL_SORT_CACHE_MAX_ENTRIES",()=>100,zx);/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Nd={kernelName:Ni,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(n,Lo(Q(e,"float32"),-1))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Bx={kernelName:$i,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>{const s=Mt(Q(e,"float32")),r=ue(lt(kt(1),s));return se(rt(n,r))}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Px={kernelName:Ti,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>{const s=ue(lt(Mt(Q(e,"float32")),1));return rt(n,s)}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Wx={kernelName:Vs,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t,r=Ct(e.shape,s.shape);return{a:()=>{let a=n;const l=Yt(e.shape,r);return l.length>0&&(a=st(a,l)),_(a,e.shape)},b:()=>{let a=n;const l=Yt(s.shape,r);return l.length>0&&(a=st(a,l)),_(a,s.shape)}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Vx={kernelName:Tc,saveAllInputs:!0,gradFunc:(n,t)=>{const e={};return t.forEach((s,r)=>{e[r]=()=>n.clone()}),e}};/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Gx={kernelName:Ci,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>wt(e)}}};/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Ux={kernelName:Ec,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>wt(e)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Hx={kernelName:Ai,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>rt(n,ue(lt(kt(1),Mt(Q(e,"float32")))))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const qx={kernelName:Ei,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>{const s=ue(X(kt(1),Mt(Q(e,"float32"))));return rt(n,s)}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const jx={kernelName:Mi,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t,r=Ct(e.shape,s.shape);return{a:()=>{const a=X(Mt(e),Mt(s));let l=D(n,rt(s,a));const c=Yt(e.shape,r);return c.length>0&&(l=st(l,c)),_(l,e.shape)},b:()=>{const a=X(Mt(e),Mt(s));let l=se(D(n,rt(e,a)));const c=Yt(s.shape,r);return c.length>0&&(l=st(l,c)),_(l,s.shape)}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Kx={kernelName:Di,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>rt(n,X(Mt(Q(e,"float32")),1))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Xx={kernelName:Fi,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>rt(n,lt(kt(1),Mt(Q(e,"float32"))))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Zx(n,t,e,s,r,o){const i=E(n,"dy","avgPool3dGrad"),a=E(t,"input","avgPool3dGrad");let l=i,c=a,u=!1;a.rank===4&&(u=!0,l=_(i,[1,i.shape[0],i.shape[1],i.shape[2],i.shape[3]]),c=_(a,[1,a.shape[0],a.shape[1],a.shape[2],a.shape[3]])),v(l.rank===5,()=>`Error in avgPool3dGrad: dy must be rank 5 but got rank ${l.rank}.`),v(c.rank===5,()=>`Error in avgPool3dGrad: input must be rank 5 but got rank ${c.rank}.`),be("avgPool3dGrad",r,o);const h={dy:l,input:c},d={filterSize:e,strides:s,pad:r,dimRoundingMode:o},f=R.runKernel(Fc,h,d);return u?_(f,[f.shape[1],f.shape[2],f.shape[3],f.shape[4]]):f}const Jx=P({avgPool3dGrad_:Zx});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Yx={kernelName:zi,inputsToSave:["x"],gradFunc:(n,t,e)=>{const[s]=t,{filterSize:r,strides:o,pad:i,dimRoundingMode:a}=e;return{x:()=>Jx(n,s,r,o,i,a)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Qx(n,t,e,s,r){const o=E(n,"dy","avgPoolGrad"),i=E(t,"input","avgPoolGrad");v(i.rank===o.rank,()=>`Rank of input (${i.rank}) does not match rank of dy (${o.rank})`);let a=i,l=o,c=!1;i.rank===3&&(c=!0,a=_(i,[1,i.shape[0],i.shape[1],i.shape[2]]),l=_(o,[1,o.shape[0],o.shape[1],o.shape[2]])),v(l.rank===4,()=>`Error in avgPoolGrad: dy must be rank 4 but got rank ${l.rank}.`),v(a.rank===4,()=>`Error in avgPoolGrad: input must be rank 4 but got rank ${a.rank}.`);const u={dy:l,input:a},h={filterSize:e,strides:s,pad:r},d=R.runKernel(Dc,u,h);return c?_(d,[d.shape[1],d.shape[2],d.shape[3]]):d}const tI=P({avgPoolGrad_:Qx});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const eI={kernelName:Ri,inputsToSave:["x"],gradFunc:(n,t,e)=>{const[s]=t,{filterSize:r,strides:o,pad:i}=e;return{x:()=>tI(n,s,r,o,i)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const nI={kernelName:Li,inputsToSave:["a","b"],gradFunc:(n,t,e)=>{const[s,r]=t,{transposeA:o,transposeB:i}=e;return!o&&!i?{a:()=>Tt(n,r,!1,!0),b:()=>Tt(s,n,!0,!1)}:!o&&i?{a:()=>Tt(n,r,!1,!1),b:()=>Tt(n,s,!0,!1)}:o&&!i?{a:()=>Tt(r,n,!1,!0),b:()=>Tt(s,n,!1,!1)}:{a:()=>Tt(r,n,!0,!0),b:()=>Tt(n,s,!0,!0)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const sI={kernelName:Oi,gradFunc:(n,t,e)=>{const{blockShape:s,crops:r}=e;return{x:()=>V0(n,s,r)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const rI={kernelName:Wm,gradFunc:(n,t,e)=>{const s=e,r=s.inputShape,o=s.shape,i=Array.from(o);for(let l=r.length-1;l>=0;l--)if(r[l]===o[l])i[l]=1;else if(r[l]!==1)throw new Error(`broadcastTo(): [${r}] cannot be broadcast to [${o}].`);const a=[];for(let l=0;l<i.length;l++)i[l]>1&&a.push(l);return{x:()=>st(n,a,!0)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const oI={kernelName:Ar,gradFunc:n=>({x:()=>n.clone()})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const iI={kernelName:_i,gradFunc:n=>({x:()=>wt(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const aI={kernelName:Er,inputsToSave:["x"],gradFunc:(n,t,e)=>{const[s]=t,{clipValueMin:r,clipValueMax:o}=e;return{x:()=>ye(Ns(vs(s,r),er(s,o)),n,wt(n))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const lI={kernelName:Bi,inputsToSave:["x"],gradFunc:Nd.gradFunc};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const cI={kernelName:Pi,saveAllInputs:!0,gradFunc:(n,t,e)=>{const s=t.map(l=>l.shape),{axis:r}=e,o=Ft(r,t[0].shape)[0],i=s.map(l=>l[o]);return en(n,i,o).map(l=>()=>l)}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const uI={kernelName:Wi,inputsToSave:["x","filter"],gradFunc:(n,t,e)=>{const[s,r]=t,{dilations:o,strides:i,pad:a,dataFormat:l}=e;return v(ks(o),()=>`Error in gradient of conv2D: dilation rates greater than 1 are not yet supported in gradients. Got dilations '${o}'`),{x:()=>il(s.shape,n,r,i,a,l),filter:()=>wl(s,n,r.shape,i,a,l)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const hI={kernelName:Vi,inputsToSave:["dy","filter"],gradFunc:(n,t,e)=>{const[s,r]=t,{strides:o,pad:i,dataFormat:a,dimRoundingMode:l}=e;return{dy:()=>Is(n,r,o,i,a,1,l),filter:()=>wl(n,s,r.shape,o,i,a,l)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function dI(n,t,e,s,r){let o=n;n.rank===4&&(o=_(n,[1,n.shape[0],n.shape[1],n.shape[2],n.shape[3]]));let i=t;i.rank===4&&(i=_(t,[1,t.shape[0],t.shape[1],t.shape[2],t.shape[3]])),v(o.rank===5,()=>`Error in conv3dDerFilter: input must be rank 5, but got shape ${o.shape}.`),v(i.rank===5,()=>`Error in conv3dDerFilter: dy must be rank 5, but got shape ${i.shape}.`),v(e.length===5,()=>`Error in conv3dDerFilter: filterShape must be length 5, but got ${e}.`),v(o.shape[4]===e[3],()=>`Error in conv3dDerFilter: depth of input ${o.shape[4]}) must match input depth in filter (${e[3]}.`),v(i.shape[4]===e[4],()=>`Error in conv3dDerFilter: depth of dy (${i.shape[4]}) must match output depth for filter (${e[4]}).`);const a={x:o,dy:i},l={strides:s,pad:r,filterShape:e};return R.runKernel(Oc,a,l)}const fI=P({conv3DBackpropFilter_:dI});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const pI={kernelName:Gi,inputsToSave:["x","filter"],gradFunc:(n,t,e)=>{const{dilations:s,strides:r,pad:o}=e;v(ks(s),()=>`Error in gradient of conv3D: dilation rates greater than 1 are not yet supported in gradients. Got dilations '${s}'`);const[i,a]=t;return{x:()=>Yu(i.shape,n,a,r,o),filter:()=>fI(i,n,a.shape,r,o)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const mI={kernelName:Dr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(se(Tw(Q(e,"float32"))),n)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const gI={kernelName:Fr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(Aw(Q(e,"float32")),n)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const bI={kernelName:Ui,inputsToSave:["x"],gradFunc:(n,t,e)=>{const[s]=t,{axis:r,exclusive:o,reverse:i}=e;return{x:()=>{const a=Ce([r],s.rank);let l=Oy(n,r,o,!i);return a!=null&&(l=bt(l,a)),l}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const yI={kernelName:Hi,inputsToSave:["x","filter"],gradFunc:(n,t,e)=>{const{dilations:s,strides:r,pad:o,dimRoundingMode:i}=e,a=s??[1,1];v(ks(a),()=>`Error in gradient of depthwiseConv2dNative: dilation rates greater than 1 are not yet supported. Got dilations '${a}'`);const[l,c]=t;return v(l.rank===4,()=>`Error in gradient of depthwiseConv2dNative: input must be rank 4, but got rank ${l.rank}.`),v(c.rank===4,()=>`Error in gradient of depthwiseConv2dNative: filter must be rank 4, but got rank ${c.rank}.`),v(l.shape[3]===c.shape[2],()=>`Error in gradient of depthwiseConv2d: number of input channels (${l.shape[3]}) must match the inChannels dimension in filter ${c.shape[2]}.`),v(Ze(r,a),()=>`Error in gradient of depthwiseConv2d: Either strides or dilations must be  1. Got strides ${r} and dilations '${a}'.`),be("depthwiseConv2d",o,i),{x:()=>e1(l.shape,n,c,r,o,a,i),filter:()=>Qw(l,n,c.shape,r,o,a,i)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const wI={kernelName:Uc,inputsToSave:["x","filter"],gradFunc:(n,t,e)=>{const[s,r]=t,o={x:s,filter:r,dy:n},i={x:s,filter:r,dy:n};return{x:()=>R.runKernel(qi,o,e),filter:()=>R.runKernel(ji,i,e)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const kI={kernelName:Rr,outputsToSave:[!0],gradFunc:(n,t)=>{const[e]=t,s={dy:n,y:e};return{x:()=>R.runKernel(qc,s)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const xI={kernelName:zr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t,s=D(mn(se(Mt(e))),2/Math.sqrt(Math.PI));return{x:()=>D(n,s)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const II={kernelName:Lr,outputsToSave:[!0],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(n,e)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const SI={kernelName:Xi,inputsToSave:["input"],gradFunc:(n,t)=>{const[e]=t;return{input:()=>_(n,e.shape)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const vI={kernelName:Zi,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(n,mn(e))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const NI={kernelName:Or,gradFunc:n=>({x:()=>wt(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const $I={kernelName:_r,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t,r=Ct(e.shape,s.shape);return{a:()=>{const a=rt(n,Q(s,"float32")),l=Yt(e.shape,r);return l.length>0?_(st(a,l),e.shape):a},b:()=>{let a=D(n,Q(e,"float32"));const l=Yt(s.shape,r);l.length>0&&(a=_(st(a,l),s.shape));const c=Mt(s);return se(rt(a,Q(c,"float32")))}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const TI={kernelName:Ji,inputsToSave:["x","mean","variance","scale"],gradFunc:(n,t,e)=>{const{varianceEpsilon:s}=e,[r,o,i,a]=t,l=a??kt(1),c=Yt(o.shape,r.shape),u=[];if(o.rank===1){for(let w=0;w<r.shape.length-1;++w)u.push(r.shape[w]);u.push(1)}const h=lt(r,o),d=D(n,l),f=xw(X(i,kt(s))),p=D(D(D(f,f),f),kt(-.5));return{x:()=>o.rank===1?_(D(D(n,tn(_(f,[1,1,1,o.shape[0]]),u)),l),r.shape):_(D(D(n,f),l),r.shape),mean:()=>{let w=D(D(f,kt(-1)),d);return o.rank===1&&(w=st(w,c)),_(w,o.shape)},variance:()=>{let w=D(D(p,h),d);return o.rank===1&&(w=st(w,c)),_(w,o.shape)},scale:()=>{const w=D(h,f);let I=D(n,w);return o.rank===1&&(I=st(I,c)),_(I,o.shape)},offset:()=>{let w=n;return o.rank===1&&(w=st(w,c)),_(w,o.shape)}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const CI={kernelName:Yi,inputsToSave:["x","indices"],gradFunc:(n,t,e)=>{const[s,r]=t,{axis:o,batchDims:i}=e,a=Ft(o,s.shape)[0],l=(c,u,h)=>()=>{const d=c.shape,f=u.size,p=d.slice(0,a),g=p.length,m=d.slice(o,d.length).slice(1),b=m.length,y=$d(0,g),k=$d(g+1,g+1+b),w=Td([p,[f],m]),I=_(h,w),S=_(u,[f]),T=Td([[g],y,k]),C=bt(I,T);let N=Ww(C,S,c.shape[a]);const $=tr(T);return N=bt(N,$),N};if(i===1){const c=s.shape[0],u=s.split(c,0);return{x:()=>An(u.map((f,p)=>l(f,r.slice(p,1),n.slice(p,1))())).reshape(s.shape),indices:()=>r}}else return{x:l(s,r,n),indices:()=>r}}};function $d(n,t){const e=[];for(let s=n;s<t;++s)e.push(s);return e}function Td(n){const t=[];for(let e=0;e<n.length;++e)for(let s=0;s<n[e].length;++s)t.push(n[e][s]);return t}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const AI={kernelName:Br,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t;return{a:()=>wt(e),b:()=>wt(s)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const EI={kernelName:Pr,gradFunc:n=>({x:()=>Q(n,"float32")})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const DI={kernelName:ta,gradFunc:n=>({x:()=>wt(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const FI={kernelName:ea,gradFunc:n=>({x:()=>wt(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const MI={kernelName:na,gradFunc:n=>({x:()=>wt(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const RI={kernelName:sa,inputsToSave:["x"],gradFunc:(n,t,e)=>{const[s]=t,{alpha:r}=e,o=Ae(s,0);return{x:()=>ye(o,n,D(n,r))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const zI={kernelName:Vr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>rt(n,X(e,1))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const LI={kernelName:Wr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>rt(n,Q(e,"float32"))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const OI={kernelName:Zm,inputsToSave:[],outputsToSave:[!0],gradFunc:(n,t,e)=>{const[s]=t,{axis:r}=e;return{logits:()=>{const i=mn(s);return lt(n,D(st(n,r,!0),i))}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function _I(n,t,e,s=5,r=1,o=1,i=.5){const a={x:n,y:t,dy:e},l={depthRadius:s,bias:r,alpha:o,beta:i};return R.runKernel(Yc,a,l)}const BI=P({localResponseNormalizationBackprop_:_I});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const PI={kernelName:Jc,inputsToSave:["x"],outputsToSave:[!0],gradFunc:(n,t,e)=>{const[s,r]=t,{depthRadius:o,bias:i,alpha:a,beta:l}=e;return{x:()=>BI(s,r,n,o,i,a,l)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Cd(n,t,e,s){return t.rank<e.rank&&(t=_(t,Te(t.shape,s))),n.rank<e.rank&&(n=_(n,Te(n.shape,s))),{x:()=>D(n,Q(Tn(e,t),n.dtype))}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Ad={kernelName:la,inputsToSave:["x"],outputsToSave:[!0],gradFunc:(n,t,e)=>{const s=e,{reductionIndices:r}=s,o=t[0],i=t[1],a=Ft(r,o.shape),l=Cd(n,i,o,a);return{x:()=>l.x()}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const WI={kernelName:Gr,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t;return{a:()=>D(n,Q(vs(e,s),"float32")),b:()=>D(n,Q(ul(e,s),"float32"))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function VI(n,t,e,s,r,o,i){const a=E(n,"dy","maxPool3dGrad"),l=E(t,"input","maxPool3dGrad"),c=E(e,"output","maxPool3dGrad");let u=a,h=l,d=c,f=!1;l.rank===4&&(f=!0,u=_(a,[1,a.shape[0],a.shape[1],a.shape[2],a.shape[3]]),h=_(l,[1,l.shape[0],l.shape[1],l.shape[2],l.shape[3]]),d=_(c,[1,c.shape[0],c.shape[1],c.shape[2],c.shape[3]])),v(u.rank===5,()=>`Error in maxPool3dGrad: dy must be rank 5 but got rank ${u.rank}.`),v(h.rank===5,()=>`Error in maxPool3dGrad: input must be rank 5 but got rank ${h.rank}.`),v(d.rank===5,()=>`Error in maxPool3dGrad: output must be rank 5 but got rank ${d.rank}.`),be("maxPool3dGrad",o,i);const p={dy:u,input:h,output:d},g={filterSize:s,strides:r,pad:o,dimRoundingMode:i},m=R.runKernel(tu,p,g);return f?_(m,[m.shape[1],m.shape[2],m.shape[3],m.shape[4]]):m}const GI=P({maxPool3dGrad_:VI});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const UI={kernelName:ua,inputsToSave:["x"],outputsToSave:[!0],gradFunc:(n,t,e)=>{const[s,r]=t,{filterSize:o,strides:i,pad:a,dimRoundingMode:l}=e;return{x:()=>GI(n,s,r,o,i,a,l)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function HI(n,t,e,s,r,o,i){const a=E(n,"dy","maxPoolGrad"),l=E(t,"input","maxPoolGrad"),c=E(e,"output","maxPoolGrad");v(l.rank===a.rank,()=>`Rank of input (${l.rank}) does not match rank of dy (${a.rank})`),v(a.rank===4,()=>`Error in maxPoolGrad: dy must be rank 4 but got rank ${a.rank}.`),v(l.rank===4,()=>`Error in maxPoolGrad: input must be rank 4 but got rank ${l.rank}.`),be("maxPoolGrad",o,i);const u={dy:a,input:l,output:c},h={filterSize:s,strides:r,pad:o,dimRoundingMode:i};return R.runKernel(Qc,u,h)}const qI=P({maxPoolGrad_:HI});/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const jI={kernelName:ca,inputsToSave:["x"],outputsToSave:[!0],gradFunc:(n,t,e)=>{const[s,r]=t,{filterSize:o,strides:i,pad:a}=e;return{x:()=>qI(n,s,r,o,i,a)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const KI={kernelName:ha,inputsToSave:["x"],gradFunc:(n,t,e)=>{const[s]=t,{axis:r}=e,o=Ft(r,s.shape),a=Je(s.shape,o)[1],l=Z(a);return{x:()=>{const u=s.shape.slice();o.forEach(f=>{u[f]=1});const h=_(n,u);return rt(D(h,Cn(s.shape,"float32")),l)}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const XI={kernelName:da,inputsToSave:["x"],outputsToSave:[!0],gradFunc:(n,t,e)=>{const s=e,{axis:r}=s,[o,i]=t,a=Ft(r,o.shape),l=Cd(n,i,o,a);return{x:()=>l.x()}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const ZI={kernelName:Ur,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t;return{a:()=>D(n,Q(er(e,s),"float32")),b:()=>D(n,Q(Ae(e,s),"float32"))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const JI={kernelName:eu,inputsToSave:["x"],gradFunc:(n,t,e)=>{const s=t[0],{paddings:r}=e,o=r.map(i=>i[0]);return{x:()=>Bt(n,o,s.shape)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const YI={kernelName:fa,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t,r=Ct(e.shape,s.shape);return{a:()=>{const a=Yt(e.shape,r);return a.length>0?_(st(n,a),e.shape):n},b:()=>{const a=D(n,se(cl(rt(e,s)))),l=Yt(s.shape,r);return l.length>0?_(st(a,l),s.shape):a}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const QI={kernelName:Hr,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t,r=Ct(e.shape,s.shape);return{a:()=>{const a=D(n,Q(s,"float32")),l=Yt(e.shape,r);return l.length>0?_(st(a,l),e.shape):a},b:()=>{const a=D(n,Q(e,"float32")),l=Yt(s.shape,r);return l.length>0?_(st(a,l),s.shape):a}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const tS={kernelName:pa,gradFunc:n=>({x:()=>se(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const eS={kernelName:ba,inputsToSave:["indices"],gradFunc:(n,t)=>{const e=t[0];return{indices:()=>ae(e.shape,"float32")}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const nS={kernelName:ga,gradFunc:n=>({x:()=>wt(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const sS={kernelName:ya,saveAllInputs:!0,gradFunc:(n,t,e)=>{const{axis:s}=e;return Ts(n,s).map(o=>()=>o)}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Ed={kernelName:wa,inputsToSave:["x"],gradFunc:(n,t,e)=>{const s=t[0],{paddings:r}=e,o=r.map(i=>i[0]);return{x:()=>Bt(n,o,s.shape)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const rS={kernelName:qr,inputsToSave:["a","b"],outputsToSave:[!0],gradFunc:(n,t)=>{const[e,s,r]=t,o=e,i=s,a=Ct(o.shape,i.shape);return{a:()=>{const u=Q(i,"float32");let h=D(n,D(u,Ss(o,lt(u,kt(1)))));const d=Yt(o.shape,a);return d.length>0&&(h=st(h,d)),_(h,o.shape)},b:()=>{const u=Ae(o,0),h=ye(u,gn(o),wt(o));let d=D(n,D(r,h));const f=Yt(i.shape,a);return f.length>0&&(d=st(d,f)),_(d,i.shape)}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const oS={kernelName:ka,inputsToSave:["x","alpha"],gradFunc:(n,t)=>{const[e,s]=t,r=Ae(e,0);return{x:()=>ye(r,n,D(n,s)),alpha:()=>{let o=ye(r,wt(n),D(n,e));const i=Yt(s.shape,n.shape);return i.length>0&&(o=st(o,i)),_(o,s.shape)}}}};/**
 * @license
 * Copyright 2022 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function iS(n,t,e){const s=n.shape.slice();s[e]=1;const r=_(t,s),o=th(n,e,!0,!1),i=th(n,e,!0,!0),a=D(o,i);return D(r,a)}function aS(n,t,e){const s=n.shape.length,r=s-e.length,o=Ce(e,s);let i=n;o!=null&&(i=bt(n,o));const a=i.shape.slice(),c=a.splice(s-e.length,e.length).reduce((d,f)=>d*f,1);a.push(c);const u=i.reshape(a);let h=iS(u,t,r);if(h=h.reshape(i.shape),o!=null){const d=tr(o);h=bt(h,d)}return h}const lS={kernelName:ou,inputsToSave:["x"],gradFunc:(n,t,e)=>{const[s]=t,{axis:r}=e;let o=[];return r==null?o=s.shape.map((i,a)=>a):typeof r=="number"?o=[r]:o=r,{x:()=>aS(s,n,o)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const cS={kernelName:Mr,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t,r=Ct(e.shape,s.shape);return{a:()=>{const a=rt(n,Q(s,"float32")),l=Yt(e.shape,r);return l.length>0?_(st(a,l),e.shape):a},b:()=>{let a=D(n,Q(e,"float32"));const l=Yt(s.shape,r);l.length>0&&(a=_(st(a,l),s.shape));const c=Mt(s);return se(rt(a,Q(c,"float32")))}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const uS={kernelName:xa,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>rt(n,se(Mt(e)))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const hS={kernelName:Kr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t,s=D(er(e,6),Lo(e));return{x:()=>D(n,Q(s,"float32"))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const dS={kernelName:jr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(n,Q(Lo(e),"float32"))}}};/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const fS={kernelName:Ia,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>_(n,e.shape)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const pS={kernelName:va,inputsToSave:["images"],gradFunc:(n,t,e)=>{const[s]=t,r={dy:n,images:s};return{images:()=>R.runKernel(cu,r,e)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const mS={kernelName:Sa,inputsToSave:["images"],gradFunc:(n,t,e)=>{const[s]=t,r={dy:n,images:s};return{images:()=>R.runKernel(lu,r,e)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const gS={kernelName:Na,gradFunc:(n,t,e)=>{const{dims:s}=e,r=Ft(s,n.shape);return{x:()=>Mo(n,r)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const bS={kernelName:Xr,gradFunc:n=>({x:()=>wt(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const yS={kernelName:Zr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>se(rt(n,D(Ss(e,1.5),2)))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const wS={kernelName:$a,inputsToSave:["condition"],gradFunc:(n,t)=>{const[e]=t;return{condition:()=>Q(wt(e),"float32"),t:()=>D(n,Q(e,n.dtype)),e:()=>D(n,Q(T0(e),n.dtype))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const kS={kernelName:Jr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>{const s=Ae(e,kt(0)),r=kt(Kh),o=kt(Xh),i=D(n,o),a=D(D(n,r),mn(Q(e,"float32")));return ye(s,i,a)}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const xS={kernelName:to,outputsToSave:[!0],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(n,D(e,lt(kt(1),e)))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const IS={kernelName:Ca,gradFunc:n=>({x:()=>wt(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const SS={kernelName:Yr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(Qu(Q(e,"float32")),n)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const vS={kernelName:Qr,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(Ry(Q(e,"float32")),n)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const NS={kernelName:Ta,inputsToSave:["x"],gradFunc:(n,t,e)=>{const[s]=t,{begin:r,size:o}=e,i=s.shape,[a,l]=Gh(s,r,o),c=[];for(let u=0;u<n.rank;u++)c.push([a[u],i[u]-a[u]-l[u]]);return{x:()=>ch(n,c)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const $S={kernelName:Fa,outputsToSave:[!0],gradFunc:(n,t,e)=>{const[s]=t,{dim:r}=e,o=!0,i=D(n,s);return{logits:()=>lt(i,D(st(i,[r],o),s))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const TS={kernelName:eo,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(n,xo(e))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Dd={kernelName:Ea,gradFunc:(n,t,e)=>{const{blockShape:s,paddings:r}=e;return{x:()=>ty(n,s,r)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Fd={kernelName:Da,gradFunc:(n,t,e)=>{const{axis:s}=e;return{x:()=>_e(n,s)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const CS={kernelName:no,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>rt(n,D(ue(Q(e,"float32")),2))}}};/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const AS={kernelName:uu,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(n,D(Q(e,"float32"),2))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const ES={kernelName:Ma,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t,r=kt(2);return{a:()=>D(n,D(r,lt(e,s))),b:()=>D(n,D(r,lt(s,e)))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const DS={kernelName:io,gradFunc:n=>({x:()=>wt(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const FS={kernelName:so,inputsToSave:["a","b"],gradFunc:(n,t)=>{const[e,s]=t,r=Ct(e.shape,s.shape);return{a:()=>{let a=n;const l=Yt(e.shape,r);return l.length>0&&(a=st(a,l)),_(a,e.shape)},b:()=>{let a=n;const l=Yt(s.shape,r);return l.length>0&&(a=st(a,l)),_(se(a),s.shape)}}}};/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const MS={kernelName:Aa,inputsToSave:["x"],gradFunc:(n,t,e)=>{const[s]=t,r=s.shape.slice(),{axis:o}=e;Ft(o,s.shape).forEach(c=>{r[c]=1});const a=_(n,r),l=D(a,Cn(s.shape,"float32"));return{x:()=>l}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const RS={kernelName:Ra,inputsToSave:["x"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>rt(n,Mt(Qu(e)))}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const zS={kernelName:ro,outputsToSave:[!0],gradFunc:(n,t)=>{const[e]=t;return{x:()=>D(lt(kt(1),Mt(e)),n)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const LS={kernelName:oo,inputsToSave:["x"],gradFunc:(n,t,e)=>{const[s]=t,{reps:r}=e;return{x:()=>{let i=wt(s);if(s.rank===1)for(let a=0;a<r[0];++a)i=X(i,Bt(n,[a*s.shape[0]],[s.shape[0]]));else if(s.rank===2)for(let a=0;a<r[0];++a)for(let l=0;l<r[1];++l)i=X(i,Bt(n,[a*s.shape[0],l*s.shape[1]],[s.shape[0],s.shape[1]]));else if(s.rank===3)for(let a=0;a<r[0];++a)for(let l=0;l<r[1];++l)for(let c=0;c<r[2];++c)i=X(i,Bt(n,[a*s.shape[0],l*s.shape[1],c*s.shape[2]],[s.shape[0],s.shape[1],s.shape[2]]));else if(s.rank===4)for(let a=0;a<r[0];++a)for(let l=0;l<r[1];++l)for(let c=0;c<r[2];++c)for(let u=0;u<r[3];++u)i=X(i,Bt(n,[a*s.shape[0],l*s.shape[1],c*s.shape[2],u*s.shape[3]],[s.shape[0],s.shape[1],s.shape[2],s.shape[3]]));else throw new Error(`Gradient for tile operation is not implemented for rank-${s.rank} tensors yet.`);return i}}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const OS={kernelName:Gs,gradFunc:(n,t,e)=>{const s=e,{perm:r}=s,o=tr(r);return{x:()=>bt(n,o)}}};/**
 * @license
 * Copyright 2020 Google Inc. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const _S={kernelName:za,gradFunc:(n,t,e)=>{const s=e,{axis:r}=s;return{value:()=>An(n,r)}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const BS={kernelName:La,inputsToSave:["segmentIds"],gradFunc:(n,t)=>{const[e]=t;return{x:()=>PS(n,e)}}};function PS(n,t){const e=es(t,wt(t)),s=ah(n,e);let r=vs(t,kt(0,"int32"));const o=s.rank-r.rank;for(let a=0;a<o;++a)r=we(r,a+1);r=Ns(r,Cn(s.shape,"bool"));const i=wt(s);return ye(r,s,i)}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const WS={kernelName:Oa,gradFunc:n=>({x:()=>wt(n)})};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const VS=[Nd,Bx,Px,Wx,Vx,Gx,Ux,Hx,qx,jx,Kx,Xx,Yx,eI,nI,sI,rI,oI,iI,aI,lI,cI,hI,uI,pI,mI,gI,bI,yI,wI,cS,kI,xI,II,SI,vI,$I,NI,TI,CI,AI,EI,DI,FI,MI,RI,zI,LI,OI,PI,Ad,Ad,WI,UI,jI,KI,XI,ZI,JI,YI,QI,tS,eS,nS,sS,Ed,Ed,rS,oS,lS,uS,hS,dS,fS,pS,mS,gS,bS,yS,wS,kS,xS,IS,SS,vS,NS,$S,TS,Dd,Dd,Fd,Fd,CS,ES,AS,DS,FS,MS,RS,zS,LS,OS,_S,BS,WS];for(const n of VS)yg(n);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Hl(n,t){return z(()=>ue(st(D(n,n),t,!0)))}class fr extends As{getConfig(){return{}}}class Md extends fr{constructor(t){super(),this.defaultMaxValue=2,this.defaultAxis=0,this.maxValue=t.maxValue!=null?t.maxValue:this.defaultMaxValue,this.axis=t.axis!=null?t.axis:this.defaultAxis}apply(t){return z(()=>{const e=Hl(t,this.axis),s=$e(e,0,this.maxValue);return D(t,rt(s,X(Ht(),e)))})}getConfig(){return{maxValue:this.maxValue,axis:this.axis}}}Md.className="MaxNorm",H(Md);class Rd extends fr{constructor(t){super(),this.defaultAxis=0,this.axis=t.axis!=null?t.axis:this.defaultAxis}apply(t){return z(()=>rt(t,X(Ht(),Hl(t,this.axis))))}getConfig(){return{axis:this.axis}}}Rd.className="UnitNorm",H(Rd);class zd extends fr{apply(t){return $s(t)}}zd.className="NonNeg",H(zd);class Ld extends fr{constructor(t){super(),this.defaultMinValue=0,this.defaultMaxValue=1,this.defaultRate=1,this.defaultAxis=0,this.minValue=t.minValue!=null?t.minValue:this.defaultMinValue,this.maxValue=t.maxValue!=null?t.maxValue:this.defaultMaxValue,this.rate=t.rate!=null?t.rate:this.defaultRate,this.axis=t.axis!=null?t.axis:this.defaultAxis}apply(t){return z(()=>{const e=Hl(t,this.axis),s=X(D(this.rate,$e(e,this.minValue,this.maxValue)),D(1-this.rate,e));return D(t,rt(s,X(Ht(),e)))})}getConfig(){return{minValue:this.minValue,maxValue:this.maxValue,rate:this.rate,axis:this.axis}}}Ld.className="MinMaxNorm",H(Ld);const Od={maxNorm:"MaxNorm",minMaxNorm:"MinMaxNorm",nonNeg:"NonNeg",unitNorm:"UnitNorm"};function jt(n){return Tl(n)}function _d(n,t={}){return ir(n,Ee.getMap().classNameMap,t,"constraint")}function Kt(n){if(n==null)return null;if(typeof n=="string"){const e={className:n in Od?Od[n]:n,config:{}};return _d(e)}else return n instanceof fr?n:_d(n)}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */async function as(n){if(n==null)return;const t=[],e=[],s=[];for(const r in n){const o=n[r];if(typeof o!="number"){const i=o;t.push(i.data()),e.push(r),s.push(i)}}if(t.length>0){const r=await Promise.all(t);for(let o=0;o<r.length;++o)n[e[o]]=r[o][0];dt(s)}}function Bd(n){if(n!=null)for(const t in n){const e=n[t];typeof e!="number"&&e.dispose()}}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */var Pd;(function(n){n[n.SILENT=0]="SILENT",n[n.VERBOSE=1]="VERBOSE"})(Pd||(Pd={}));const GS=125;class pr{constructor(){this.validationData=null}setParams(t){this.params=t}async onEpochBegin(t,e){}async onEpochEnd(t,e){}async onBatchBegin(t,e){}async onBatchEnd(t,e){}async onTrainBegin(t){}async onTrainEnd(t){}setModel(t){}}class US{constructor(t,e=10){t==null&&(t=[]),this.callbacks=t,this.queueLength=e}append(t){this.callbacks.push(t)}setParams(t){for(const e of this.callbacks)e.setParams(t)}setModel(t){for(const e of this.callbacks)e.setModel(t)}async onEpochBegin(t,e){e==null&&(e={});for(const s of this.callbacks)await s.onEpochBegin(t,e)}async onEpochEnd(t,e){e==null&&(e={});for(const s of this.callbacks)await s.onEpochEnd(t,e)}async onBatchBegin(t,e){e==null&&(e={});for(const s of this.callbacks)await s.onBatchBegin(t,e)}async onBatchEnd(t,e){e==null&&(e={});for(const s of this.callbacks)await s.onBatchEnd(t,e)}async onTrainBegin(t){t==null&&(t={});for(const e of this.callbacks)await e.onTrainBegin(t)}async onTrainEnd(t){t==null&&(t={});for(const e of this.callbacks)await e.onTrainEnd(t)}}class HS extends pr{constructor(){super()}async onEpochBegin(t){this.seen=0,this.totals={}}async onBatchEnd(t,e){e==null&&(e={});const s=e.size==null?0:e.size;this.seen+=s;for(const r in e){const o=e[r];if(typeof o=="number")this.totals.hasOwnProperty(r)||(this.totals[r]=0),this.totals[r]=this.totals[r]+o*s;else{let i;r in this.totals?i=this.totals[r]:this.totals[r]=0;const a=z(()=>X(this.totals[r],D(o,s)));this.totals[r]=a,i!=null&&i.dispose()}}}async onEpochEnd(t,e){if(e!=null)for(const s of this.params.metrics)this.totals[s]!=null&&(typeof this.totals[s]=="number"?e[s]=this.totals[s]/this.seen:z(()=>{const r=D(rt(1,this.seen),this.totals[s]);e[s]=r,this.totals[s].dispose(),Ke(e[s])}))}}class qS extends pr{async onTrainBegin(t){this.epoch=[],this.history={}}async onEpochEnd(t,e){e==null&&(e={}),this.epoch.push(t);for(const s in e)this.history[s]==null&&(this.history[s]=[]),this.history[s].push(e[s])}async syncData(){const t=[],e=[],s=[];for(const o in this.history){const i=this.history[o];for(let a=0;a<i.length;++a)if(typeof i[a]!="number"){const l=i[a];t.push(l.data()),e.push(o),s.push(a)}}const r=await Promise.all(t);for(let o=0;o<r.length;++o)this.history[e[o]][s[o]].dispose(),this.history[e[o]][s[o]]=r[o][0]}}class jS extends pr{constructor(t,e){if(super(),this.currentEpoch=0,this.nowFunc=t.nowFunc,this.nextFrameFunc=t.nextFrameFunc||fk,this.yieldEvery=e||"auto",this.yieldEvery==="auto"&&(this.yieldEvery=GS),this.yieldEvery==="never"&&t.onYield!=null)throw new Error("yieldEvery is `never` but you provided an `onYield` callback. Either change `yieldEvery` or remove the callback");wi(this.yieldEvery)&&(this.maybeWait=sx(this.maybeWait.bind(this),this.yieldEvery,this.nowFunc)),this.trainBegin=t.onTrainBegin,this.trainEnd=t.onTrainEnd,this.epochBegin=t.onEpochBegin,this.epochEnd=t.onEpochEnd,this.batchBegin=t.onBatchBegin,this.batchEnd=t.onBatchEnd,this.yield=t.onYield}async maybeWait(t,e,s){const r=[];this.yield!=null&&(await as(s),r.push(this.yield(t,e,s))),r.push(this.nextFrameFunc()),await Promise.all(r)}async onEpochBegin(t,e){this.currentEpoch=t,this.epochBegin!=null&&(await as(e),await this.epochBegin(t,e))}async onEpochEnd(t,e){const s=[];this.epochEnd!=null&&(await as(e),s.push(this.epochEnd(t,e))),this.yieldEvery==="epoch"&&s.push(this.nextFrameFunc()),await Promise.all(s)}async onBatchBegin(t,e){this.batchBegin!=null&&(await as(e),await this.batchBegin(t,e))}async onBatchEnd(t,e){const s=[];this.batchEnd!=null&&(await as(e),s.push(this.batchEnd(t,e))),this.yieldEvery==="batch"?s.push(this.nextFrameFunc()):wi(this.yieldEvery)&&s.push(this.maybeWait(this.currentEpoch,t,e)),await Promise.all(s)}async onTrainBegin(t){this.trainBegin!=null&&(await as(t),await this.trainBegin(t))}async onTrainEnd(t){this.trainEnd!=null&&(await as(t),await this.trainEnd(t))}}function Wd(n,t){return n==null&&(n={}),n instanceof pr?[n]:Array.isArray(n)&&n[0]instanceof pr?n:xt(n).map(s=>new jS(s,t))}class Re{constructor(){}static registerCallbackConstructor(t,e){v(t>=0&&Number.isInteger(t),()=>`Verbosity level is expected to be an integer >= 0, but got ${t}`),Re.checkForDuplicate(e),Re.constructors[t]==null&&(Re.constructors[t]=[]),Re.constructors[t].push(e)}static checkForDuplicate(t){for(const e in Re.constructors)Re.constructors[+e].forEach(r=>{if(r===t)throw new A("Duplicate callback constructor.")})}static clear(){Re.constructors={}}static createCallbacks(t){const e=[];for(const s in Re.constructors){const r=+s;t>=r&&e.push(...Re.constructors[r])}return e.map(s=>new s)}}Re.constructors={};function Vd(n,t,e,s,r,o,i,a,l){const c=new qS,u=[new HS,...Re.createCallbacks(t)];n!=null&&u.push(...n),u.push(c);const h=new US(u);return h.setParams({epochs:e,initialEpoch:s,samples:r,steps:o,batchSize:i,verbose:t,doValidation:a,metrics:l}),{callbackList:h,history:c}}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function cn(n,t={},e=!1){return ir(n,Ee.getMap().classNameMap,t,"layer",e)}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Ko(n,t){return z(()=>{n.dtype!=="float32"&&(n=Q(n,"float32"));const e=st(cr(n),t,!0),s=So(e.shape,Ht()),r=ue(es(e,s));return rt(n,r)})}function Xo(n,t){return z(()=>Ut(cr(lt(t,n)),-1))}function ql(n,t){return z(()=>Ut(fe(lt(t,n)),-1))}function jl(n,t){return z(()=>{const e=lt(n,t),s=$e(fe(n),Ht(),Number.MAX_VALUE),r=fe(rt(e,s));return D(100,Ut(r,-1))})}function KS(n,t){return z(()=>{const e=$e(t,Ht(),Number.MAX_VALUE),s=gn(X(1,e)),r=$e(n,Ht(),Number.MAX_VALUE),o=gn(X(1,r));return Ut(cr(lt(s,o)),-1)})}function XS(n,t){return z(()=>{const e=es(0,lt(1,D(n,t)));return Ut(cr(e),-1)})}function ZS(n,t){return z(()=>{const e=es(0,lt(1,D(n,t)));return Ut(e,-1)})}function JS(n,t){return z(()=>{const e=st(D(n,t),-1),s=Qe(D(lt(1,n),t),-1);return es(0,X(1,lt(s,e)))})}function YS(n,t){return z(()=>{const e=Math.log(2),s=lt(t,n),r=lt(X(s,hl(D(-2,s))),e);return Ut(r,-1)})}function mr(n,t,e=!1){return z(()=>{if(e)t=xh(t);else{const s=st(t,t.shape.length-1,!0);t=rt(t,s)}return t=$e(t,Ht(),1-Ht()),se(st(D(Q(n,"float32"),gn(t)),t.shape.length-1))})}function Zo(n,t,e=!1){return z(()=>{const s=Q(cl(mx(n)),"int32");t=$e(t,Ht(),1-Ht());const r=t.shape,o=_(_0(s,r[r.length-1]),r);return mr(o,t,e)})}function QS(n,t){if(!oe(n.shape,t.shape))throw new A(`logits and labels must have the same shape, but got shapes ${JSON.stringify(n.shape)} and ${JSON.stringify(t.shape)}`);return z(()=>{const e=$s(t),s=se(fe(t));return X(lt(e,D(t,n)),g0(mn(s)))})}function Jo(n,t){return z(()=>{let e;return e=$e(t,Ht(),1-Ht()),e=gn(rt(e,lt(1,e))),Ut(QS(n,e),-1)})}function tv(n,t){return z(()=>{const e=$e(n,Ht(),1),s=$e(t,Ht(),1);return st(D(n,gn(rt(e,s))),-1)})}function ev(n,t){return z(()=>{const e=gn(X(Ht(),t));return Ut(lt(t,D(n,e)),-1)})}function Gd(n,t){return z(()=>{const e=Ko(n,-1),s=Ko(t,-1),r=D(e,s);return se(st(r,-1))})}const Yo={meanSquaredError:Xo,meanAbsoluteError:ql,meanAbsolutePercentageError:jl,meanSquaredLogarithmicError:KS,squaredHinge:XS,hinge:ZS,categoricalHinge:JS,logcosh:YS,categoricalCrossentropy:mr,sparseCategoricalCrossentropy:Zo,binaryCrossentropy:Jo,kullbackLeiblerDivergence:tv,poisson:ev,cosineProximity:Gd};function Kl(n){if(typeof n=="string"){if(n in Yo)return Yo[n];let t=`Unknown loss ${n}`;throw n.toLowerCase().includes("softmaxcrossentropy")&&(t=`Unknown loss ${n}. Use "categoricalCrossentropy" as the string name for tf.losses.softmaxCrossEntropy`),new A(t)}else return n}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Ud(n,t){return z(()=>{const e=D(.5,Be(t)),s=on(Ae(t,e),n.dtype);return Ut(Tn(n,s),-1)})}function Hd(n,t){return z(()=>on(Tn(bo(n,-1),bo(t,-1)),"float32"))}function nv(n,t){return z(()=>Q(st(Ns(Tn(n,1),Tn(t,1))),"float32"))}function sv(n,t){return z(()=>Q(st(Ns(Tn(n,0),Tn(t,1))),"float32"))}function rv(n,t){return z(()=>{const e=nv(n,t),s=sv(n,t),r=X(e,s);return Q(ye(Ae(r,0),rt(e,r),0),"float32")})}function ov(n,t){return Jo(n,t)}function iv(n,t){return n.rank===t.rank&&(n=zo(n,[n.rank-1])),t=bo(t,-1),t.dtype!==n.dtype&&(t=Q(t,n.dtype)),Q(Tn(n,t),"float32")}const av=Xo,lv=Xo,cv=ql,uv=ql,hv=jl,dv=jl,qd=mr,fv=Gd,jd=Zo,Qo={binaryAccuracy:Ud,categoricalAccuracy:Hd,precision:rv,categoricalCrossentropy:qd,sparseCategoricalCrossentropy:jd,mse:av,MSE:lv,mae:cv,MAE:uv,mape:hv,MAPE:dv,cosine:fv};function pv(n){if(typeof n=="string"&&n in Qo)return Qo[n];if(typeof n!="string"&&n!=null)return n;throw new A(`Unknown metric ${n}`)}function ti(n){if(rn(n!==null,`Unknown LossOrMetricFn ${n}`),typeof n=="string")return n;{let t;for(const e of Object.keys(Yo))if(Yo[e]===n){t=e;break}if(t!==void 0)return t;for(const e of Object.keys(Qo))if(Qo[e]===n){t=e;break}return t!==void 0?t:n.name}}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function mv(n){const t={Adagrad:()=>Es.adagrad(.01),Adadelta:()=>Es.adadelta(1,.95,Ht()),Adam:()=>Es.adam(.001,.9,.999,Ht()),Adamax:()=>Es.adamax(.002,.9,.999,Ht(),0),RMSProp:()=>Es.rmsprop(.001,.9,0,Ht()),SGD:()=>Es.sgd(.01)};if(t.adagrad=t.Adagrad,t.adadelta=t.Adadelta,t.adam=t.Adam,t.adamax=t.Adamax,t.rmsprop=t.RMSProp,t.sgd=t.SGD,n in t)return t[n]();throw new A(`Unknown Optimizer ${n}`)}/**
 * @license
 * Copyright 2019 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */const Kd=1*1024*1024;function Xd(n,t,e=!1){if(n==null||typeof n!="object"||Object.getPrototypeOf(n)!==Object.prototype||!Xl(n))throw new Error("User-defined metadata is expected to be a JSON object, but is not.");if(e){const s=JSON.stringify(n);s.length>Kd&&console.warn(`User-defined metadata of model "${t}" is too large in size (length=${s.length} when serialized). It is not recommended to store such large objects in user-defined metadata. Please make sure its serialized length is <= ${Kd}.`)}}function Xl(n){if(n===null)return!0;if(typeof n=="object")if(Object.getPrototypeOf(n)===Object.prototype){const t=Object.keys(n);for(const e of t)if(typeof e!="string"||!Xl(n[e]))return!1;return!0}else if(Array.isArray(n)){for(const t of n)if(!Xl(t))return!1;return!0}else return!1;else{const t=typeof n;return t==="string"||t==="number"||t==="boolean"}}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function gv(n,t,e,s=console.log){const r=yv(n),o=["Layer (type)","Input Shape","Output shape","Param #"];r?(t=t||90,e=e||[.32,.61,.89,1]):(t=t||115,e=e||[.24,.48,.7,.8,1]),e[e.length-1]<=1&&(e=e.map(u=>Math.floor(t*u)));let i;if(!r){o.push("Receives inputs"),i=[];for(const u in n.nodesByDepth)i.push(...n.nodesByDepth[u])}s("_".repeat(t)),ei(o,e,s),s("=".repeat(t));const a=n.layers;for(let u=0;u<a.length;++u)r?wv(a[u],e,s):kv(a[u],e,i,s),s((u===a.length-1?"=":"_").repeat(t));n.checkTrainableWeightsConsistency();const l=bv(n),c=Uo(n.nonTrainableWeights);s(`Total params: ${l+c}`),s(`Trainable params: ${l}`),s(`Non-trainable params: ${c}`),s("_".repeat(t))}function bv(n){let t;return n.collectedTrainableWeights!=null?t=Uo(n.collectedTrainableWeights):t=Uo(n.trainableWeights),t}function yv(n){let t=!0;const e=[],s=[];for(const r in n.nodesByDepth)e.push(n.nodesByDepth[r]);for(const r of e){if(r.length>1||r.length===1&&r[0].inboundLayers.length>1){t=!1;break}s.push(...r)}if(t)for(const r of n.layers){let o=!1;for(const i of r.inboundNodes)if(s.indexOf(i)!==-1)if(o){t=!1;break}else o=!0;if(!t)break}return t}function ei(n,t,e=console.log){let s="";for(let r=0;r<n.length;++r)r>0&&(s=s.slice(0,s.length-1)+" "),s+=n[r],s=s.slice(0,t[r]),s+=" ".repeat(t[r]-s.length);e(s)}function wv(n,t,e){let s,r;try{r=n.inboundNodes.map(l=>JSON.stringify(l.inputShapes)).join(",")}catch{r="multiple"}try{s=JSON.stringify(n.outputShape)}catch{s="multiple"}const o=n.name,i=n.getClassName(),a=[`${o} (${i})`,r,s,n.countParams().toString()];ei(a,t,e)}function kv(n,t,e,s){let r,o;try{o=n.inboundNodes.map(h=>JSON.stringify(h.inputShapes)).join(",")}catch{o="multiple"}try{r=JSON.stringify(n.outputShape)}catch{r="multiple"}const i=[];for(const h of n.inboundNodes)if(!(e!=null&&e.length>0&&e.indexOf(h)===-1))for(let d=0;d<h.inboundLayers.length;++d){const f=h.inboundLayers[d].name,p=h.nodeIndices[d],g=h.tensorIndices[d];i.push(`${f}[${p}][${g}]`)}const a=n.name,l=n.getClassName(),c=i.length===0?"":i[0],u=[`${a} (${l})`,o,r,n.countParams().toString(),c];ei(u,t,s);for(let h=1;h<i.length;++h)ei(["","","","",i[h]],t,s)}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Zd(n,t,e){return(n==="inboundNodes"||n==="outputLayers"||n==="inputLayers")&&t===0&&typeof e=="string"}function ni(n,t){if(n===null)return null;if(typeof n=="string")return ss(n);if(typeof n=="number"||typeof n=="boolean")return n;if(n instanceof Array){const e=[],s=n.length;for(let r=0;r<s;++r){const o=n[r];Zd(t,r,o)?e.push(o):e.push(ni(o,t))}return e}else{const e={};for(const s of Object.keys(n)){const r=n[s];if(s==="name"&&typeof r=="string")e[s]=r;else{const o=ss(s);e[o]=ni(r,o)}}return e}}function Zl(n,t){if(n==null)return null;if(typeof n=="string")return yn(n);if(typeof n=="number"||typeof n=="boolean")return n;if(n instanceof Array){const e=[],s=n.length;for(let r=0;r<s;++r){const o=n[r];Zd(t,r,o)?e.push(o):e.push(Zl(o,t))}return e}else{const e={};for(const s of Object.keys(n)){const r=n[s],o=yn(s);(s==="name"||s==="className")&&typeof r=="string"?e[o]=r:e[o]=Zl(r,s)}return e}}/** @license See the LICENSE file. */const Jd="4.22.0";/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */const xv=n=>{const t=Object.keys(n);if(t.length===0)return!1;const e=t[0].split("/");return!isNaN(parseInt(e[e.length-1],10))};class Ge extends pt{constructor(t){if(super({}),this.containerNodes=new Set,this.name=t.name,this.name==null){const y=this.getClassName().toLowerCase();this.name=Po(y)}if(this.supportsMasking=!1,this.trainable_=!0,Array.isArray(t.inputs)?this.inputs=t.inputs.slice():this.inputs=[t.inputs],Array.isArray(t.outputs)?this.outputs=t.outputs.slice():this.outputs=[t.outputs],Dn(this.inputs).length!==this.inputs.length)throw new A(`The list of inputs passed to the model is redundant. All inputs should only appear once. Found: ${this.inputs.map(y=>y.name)}`);Dn(this.outputs).length!==this.outputs.length&&console.warn(`The list of outputs passed to the model is redundant. All outputs should only appear once. Found: ${this.outputs.map(y=>y.name)}`),this.inputLayers=[],this.inputLayersNodeIndices=[],this.inputLayersTensorIndices=[],this.outputLayers=[],this.outputLayersNodeIndices=[],this.outputLayersTensorIndices=[],this.layers=[],this.internalContainerRefs=[];for(const y of this.outputs){const k=y.sourceLayer,w=y.nodeIndex,I=y.tensorIndex;this.outputLayers.push(k),this.outputLayersNodeIndices.push(w),this.outputLayersTensorIndices.push(I)}for(const y of this.inputs){const k=y.sourceLayer,w=y.nodeIndex,I=y.tensorIndex;rn(w===0,"input layer has >1 nodes"),rn(I===0,"input layer has >1 tensors"),this.inputLayers.push(k),this.inputLayersNodeIndices.push(w),this.inputLayersTensorIndices.push(I)}this.inputNames=[],this.outputNames=[],this.feedInputShapes=[],this.feedInputNames=[],this.feedOutputNames=[];for(let y=0;y<this.inputLayers.length;y++){const k=this.inputLayers[y];if(!(k instanceof hr))throw new TypeError(`Input layers to a LayersModel must be InputLayer objects. Received inputs: ${t.inputs}. Input ${y} (0-based) originates from layer type ${k.getClassName()}.`);this.inputNames.push(k.name),this.feedInputShapes.push(k.batchInputShape),this.feedInputNames.push(k.name)}for(const y of this.outputLayers)this.outputNames.push(y.name);this.internalInputShapes=this.inputs.map(y=>y.shape),this.internalOutputShapes=this.outputs.map(y=>y.shape);const e={},s={},r={},o={},i={},a=[],l=(y,k,w,I,S,T)=>{(I==null||S==null||T==null)&&(I=y.sourceLayer,S=y.nodeIndex,T=y.tensorIndex);const C=I.inboundNodes[S];if(w.indexOf(C)!==-1)throw new De(`The tensor ${y.name} at layer "${I.name}" is part of a cycle.`);if(k.indexOf(C)!==-1)return;this.containerNodes.add(Ge.nodeKey(I,S)),I.id in i||(i[I.id]=Object.keys(i).length),w.indexOf(C)===-1&&w.push(C);const N=C.inboundLayers.length;for(let $=0;$<N;$++){const x=C.inputTensors[$],F=C.inboundLayers[$],M=C.nodeIndices[$],O=C.tensorIndices[$];l(x,k,w,F,M,O)}for(k.push(C);w.indexOf(C)>=0;)w.splice(w.indexOf(C),1);a.push(C)},c=[],u=[];for(const y of this.outputs)l(y,c,u);const h=a.slice().reverse();for(const y of h){s[y.id]=y,y.id in e||(e[y.id]=0);let k=e[y.id];const w=r[y.outboundLayer.id]==null?0:r[y.outboundLayer.id];k=Math.max(k,w),r[y.outboundLayer.id]=k,o[y.outboundLayer.id]=y.outboundLayer,e[y.id]=k;for(let I=0;I<y.inboundLayers.length;I++){const S=y.inboundLayers[I],T=y.nodeIndices[I],C=S.inboundNodes[T],N=e[C.id]==null?0:e[C.id];e[C.id]=Math.max(k+1,N),s[C.id]=C}}const d={};for(const y in e){const k=e[y];k in d||(d[k]=[]),d[k].push(s[y])}const f={};for(const y in r){const k=r[y];k in f||(f[k]=[]),f[k].push(o[y])}let p=Object.keys(f).map(y=>parseInt(y,10)).sort(_o);this.layers=[];for(const y of p){const k=f[y];k.sort((w,I)=>{const S=i[w.id],T=i[I.id];return S<T?-1:S>T?1:0});for(const w of k)w instanceof Ge&&this.internalContainerRefs.push(w),this.layers.push(w)}this.layersByDepth=f,p=Object.keys(d).map(y=>parseInt(y,10)).sort(_o);const g=this.inputs.slice(),m=[];for(const y of p)for(const k of d[y]){const w=k.outboundLayer;if(w!=null){for(const I of k.inputTensors)if(g.indexOf(I)===-1)throw new De(`Graph disconnected: cannot obtain value for tensor ${I} at layer "${w.name}". The following previous layers were accessed without issue: ${m}`);for(const I of k.outputTensors)g.push(I);m.push(w.name)}}this.nodesByDepth=d;const b=this.layers.map(y=>y.name);for(const y of b){const k=b.filter(w=>w===y).length;if(k!==1)throw new De(`The name "${y}" is used ${k} times in the model. All layer names should be unique. Layer names: `+JSON.stringify(b))}this.outboundNodes=[],this.inboundNodes=[],new Ho({outboundLayer:this,inboundLayers:[],nodeIndices:[],tensorIndices:[],inputTensors:this.inputs,outputTensors:this.outputs,inputMasks:this.inputs.map(y=>null),outputMasks:this.outputs.map(y=>null),inputShapes:this.inputs.map(y=>y.shape),outputShapes:this.outputs.map(y=>y.shape)}),this.built=!0,this._refCount=1}assertNotDisposed(){if(this._refCount===0)throw new Error(`Container '${this.name}' is already disposed.`)}dispose(){this.assertNotDisposed();const t={refCountAfterDispose:null,numDisposedVariables:0};if(--this._refCount===0){for(const e of this.layers)t.numDisposedVariables+=e.dispose().numDisposedVariables;for(const e of this.internalContainerRefs)t.numDisposedVariables+=e.dispose().numDisposedVariables}return t.refCountAfterDispose=this._refCount,t}get trainable(){return this.trainable_}set trainable(t){this.layers.forEach(e=>{e._trainableWeights.forEach(s=>s.trainable=t)}),this.trainable_=t}get trainableWeights(){if(this._trainableWeights.length>0)throw new A("Container instance unexpectedly contains _trainableWeights.The trainable weights of a Container are a union of the trainable weights of its consituent Layers. Its own _trainableWeights must remain an empty Array.");if(!this.trainable)return[];let t=[];for(const e of this.layers)t=t.concat(e.trainableWeights);return t}get nonTrainableWeights(){const t=[];for(const e of this.layers)t.push(...e.nonTrainableWeights);if(!this.trainable){const e=[];for(const s of this.layers)e.push(...s.trainableWeights);return e.concat(t)}return t}get weights(){return this.trainableWeights.concat(this.nonTrainableWeights)}loadWeights(t,e=!0){const s={};let r=0;const o=xv(t);o&&this.parseWeights(t);for(const a of this.layers)for(const[l,c]of a.weights.entries()){const u=o?`${c.name.split("/").slice(0,-1).join("/")+"/"}${l}`:c.originalName;if(s[u]!=null)throw new A(`Duplicate weight name: ${u}`);s[u]=c,r++}const i=[];for(const a in t){let l=a;if(s[a]==null){const c=a.split("/");l=c.slice(0,-2).concat([c[c.length-1]]).join("/")}if(s[l]!=null)i.push([s[l],t[a]]);else if(e)throw new A(`Provided weight data has no target variable: ${a}`);delete s[l]}if(e){const a=[];for(const l in s)a.push(l);if(a.length>0)throw new A(`${a.length} of ${r} weights are not set: ${a}`)}Ul(i)}parseWeights(t){for(const e in Object.keys(t)){const s=e.split("/"),r=["vars","layer_checkpoint_dependencies"],o=s.map(i=>i.startsWith("_")?i.slice(1):i).filter(i=>!r.includes(i)).join("/");o!==e&&(t[o]=t[e],delete t[e])}}updatedConfig(){const t=this.getConfig(),e={};return e.className=this.getClassName(),e.config=t,e.kerasVersion=`tfjs-layers ${Jd}`,e.backend="TensorFlow.js",e}toJSON(t,e=!0){const s=Zl(this.updatedConfig());return e?JSON.stringify(s):s}call(t,e){return z(()=>{t=xt(t);const s=new Rn;for(let r=0;r<this.inputs.length;++r)s.add(this.inputs[r],t[r]);return dr(this.outputs,s,e)})}computeMask(t,e){return z(()=>{t=xt(t);let s;return e==null?s=ns(null,t.length):s=xt(e),this.runInternalGraph(t,s)[1]})}computeOutputShape(t){const e=Go(t);if(e.length!==this.inputLayers.length)throw new A(`Invalid inputShape argument ${t}: model has ${this.inputLayers.length} tensor inputs.`);const s={};for(let a=0;a<e.length;a++){const l=this.inputLayers[a],c=e[a],u=l.name+"_0_0";s[u]=c}const r=Object.keys(this.nodesByDepth).map(a=>parseInt(a,10)).sort(_o);if(r.length>1)for(const a of r){const l=this.nodesByDepth[a];for(const c of l){const u=c.outboundLayer;if(this.inputLayers.map(g=>g.id).indexOf(u.id)!==-1)continue;const h=[];for(let g=0;g<c.inboundLayers.length;g++){const m=c.inboundLayers[g],b=c.nodeIndices[g],y=c.tensorIndices[g],k=`${m.name}_${b}_${y}`,w=s[k];h.push(w)}const d=u.computeOutputShape(pe(h)),f=Go(d),p=u.inboundNodes.indexOf(c);for(let g=0;g<f.length;g++){const m=`${u.name}_${p}_${g}`;s[m]=f[g]}}}const o=[],i=[];for(let a=0;a<this.outputLayers.length;a++){const l=this.outputLayers[a],c=this.outputLayersNodeIndices[a],u=this.outputLayersTensorIndices[a],h=`${l.name}_${c}_${u}`;i.push(h)}for(let a=0;a<i.length;a++){const l=i[a];rn(l in s),o.push(s[l])}return pe(o)}runInternalGraph(t,e){e==null&&(e=ns(null,t.length));const s={};for(let l=0;l<this.inputs.length;++l){const c=this.inputs[l],u=t[l],h=e[l];s[c.id]=[u,h]}const r=Object.keys(this.nodesByDepth).map(l=>parseInt(l,10)).sort(_o);for(const l of r){const c=this.nodesByDepth[l];for(const u of c){const h=u.outboundLayer,d=u.inputTensors,f=u.outputTensors,p=new Array;for(const g of d)g.id in s&&p.push(s[g.id]);if(p.length===d.length){let g={},m,b,y,k;if(u.callArgs!=null&&(g=u.callArgs),p.length===1){const[w,I]=p[0];g.mask==null&&(g.mask=I),y=xt(h.call(w,g)),k=xt(h.computeMask(w,I)),m=[w],b=[I]}else m=p.map(w=>w[0]),b=p.map(w=>w[1]),g.mask==null&&(g.mask=b),y=xt(h.call(m,g)),k=xt(h.computeMask(m,b));if(h.activityRegularizer)throw new ut("LayersModel invocation with concrete Tensor value(s) in the presence of activity regularizer(s) is not supported yet.");for(let w=0;w<f.length;++w){const I=f[w],S=y[w],T=k[w];s[I.id]=[S,T]}}}}const o=[],i=[],a=[];for(const l of this.outputs){rn(l.id in s,`Could not compute output ${l.name} : ${l.id}`);const[c,u]=s[l.id];a.push(c.shape),o.push(c),i.push(u)}return[o,i,a]}buildNodeConversionMap(t){const e={};let s;for(const r of this.layers){s=r instanceof Ge?1:0;for(let o=0;o<r.inboundNodes.length;o++){const i=Ge.nodeKey(r,o);this.containerNodes.has(i)&&(e[i]=s,s+=1)}}return e}getLayer(t,e){if(e!=null)return this.findLayer(e);if(t==null)throw new A("Provide either a layer name or layer index");if(typeof t=="number")return this.findLayer(t);for(const s of this.layers)if(s.name===t)return s;throw new A(`No such layer: ${t}`)}findLayer(t){if(this.layers.length<=t)throw new A(`Was asked to retrieve layer at index ${t}, but model only has ${this.layers.length} layer(s).`);return this.layers[t]}calculateLosses(){return z(()=>{const t=[];for(const e of this.layers)for(let s=0;s<e.inboundNodes.length;++s){const r=Ge.nodeKey(e,s);this.containerNodes.has(r)&&t.push(...e.calculateLosses())}return t})}getConfig(){const t={name:this.name},e=this.buildNodeConversionMap(this.layers),s=[];for(const i of this.layers){const a=i.getClassName(),l=i.getConfig(),c=[];for(let h=0;h<i.inboundNodes.length;h++){const d=i.inboundNodes[h],f=Ge.nodeKey(i,h);let p={};if(this.containerNodes.has(f)){if(d.callArgs)try{JSON.stringify(d.callArgs),p=d.callArgs}catch{console.warn(`Layer ${i.name} was passed non-serializable keyword arguments: ${d.callArgs}. They will not be included in the serialized model (and thus will be missing at deserialization time).`),p={}}if(d.inboundLayers.length>0){const g=[];for(let m=0;m<d.inboundLayers.length;m++){const b=d.inboundLayers[m],y=d.nodeIndices[m],k=d.tensorIndices[m],w=Ge.nodeKey(b,y);let I=e[w];I==null&&(I=0),g.push([b.name,I,k,p])}c.push(g)}}}const u={};u.name=i.name,u.className=a,u.config=l,u.inboundNodes=c,s.push(u)}t.layers=s;const r=[];for(let i=0;i<this.inputLayers.length;i++){const a=this.inputLayers[i],l=this.inputLayersNodeIndices[i],c=Ge.nodeKey(a,l);if(!this.containerNodes.has(c))continue;let u=e[c];u==null&&(u=0);const h=this.inputLayersTensorIndices[i];r.push([a.name,u,h])}t.inputLayers=r;const o=[];for(let i=0;i<this.outputLayers.length;i++){const a=this.outputLayers[i],l=this.outputLayersNodeIndices[i],c=Ge.nodeKey(a,l);if(!this.containerNodes.has(c))continue;let u=e[c];u==null&&(u=0);const h=this.outputLayersTensorIndices[i];o.push([a.name,u,h])}return t.outputLayers=o,t}static fromConfig(t,e,s={},r=!1){const o={},i={};function a(m,b){m.name in i?i[m.name].push(b):i[m.name]=[b]}function l(m,b){const y=[];let k;for(const w of b){const I=w[0],S=w[1],T=w[2];if(k=w[3]==null?{}:w[3],!(I in o)){a(m,b);return}const C=o[I];if(C.inboundNodes.length<=S){a(m,b);return}const N=C.inboundNodes[S];y.push(N.outputTensors[T])}y.length>0&&m.apply(pe(y),k)}function c(m){const b=m.name,y=cn(m,e.customObjects!=null?e.customObjects:{});y.setFastWeightInitDuringBuild(r),o[b]=y,m.inboundNodes.forEach(w=>{if(!(w instanceof Array))throw new A(`Corrupted configuration, expected array for nodeData: ${w}`);a(y,w)})}const u=e.name,h=e.layers;for(const m of h)c(m);for(;!nx(i);)for(const m of h){const b=o[m.name];if(b.name in i){const y=i[b.name];delete i[b.name];for(const k of y)l(b,k)}}const d=[],f=[],p=e.inputLayers;for(const m of p){const b=m[0],y=m[1],k=m[2];rn(b in o);const I=o[b].inboundNodes[y].outputTensors;d.push(I[k])}const g=e.outputLayers;for(const m of g){const b=m[0],y=m[1],k=m[2];rn(b in o);const I=o[b].inboundNodes[y].outputTensors;f.push(I[k])}return new t({inputs:d,outputs:f,name:u})}get stateful(){if(this._stateful)throw new A("Container instance unexpectedly has _stateful = true. The statefulness of a Container is determined by the Layers it contains. Its _stateful property must remain the default false.");for(const t of this.layers)if(t.stateful)return!0;return!1}resetStates(){z(()=>{this.layers.forEach(t=>{t.stateful&&t.resetStates()})})}}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Iv(n,t,e){const s=t.length;if(n==null||Array.isArray(n)&&n.length===0)return t.map(r=>null);if(s===1)return Array.isArray(n)&&n.length===1?n:typeof n=="object"&&t[0]in n?[n[t[0]]]:[n];if(Array.isArray(n)){if(n.length!==s)throw new Error(`Provided ${e} is an array of ${n.length} element(s), but the model has ${s} outputs. Make sure a set of weights is provided for each model output.`);return n}else if(typeof n=="object"&&Object.keys(n).length>0&&typeof n[Object.keys(n)[0]]=="object"){const r=[];return t.forEach(o=>{o in n?r.push(n[o]):r.push(null)}),r}else throw new Error(`The model has multiple (${s}) outputs, so ${e} must be either an array with ${s} elements or an object with ${t} keys. Provided ${e} not understood: ${JSON.stringify(n)}`)}function Yd(n,t){return Iv(n,t,"classWeight")}async function Qd(n,t,e,s){if(e!=null){const r=z(()=>{if(n.shape.length===1)return Qn(n);if(n.shape.length===2){if(n.shape[1]>1)return bo(n,1);if(n.shape[1]===1)return _(n,[n.shape[0]]);throw new Error(`Encountered unexpected last-dimension size (${n.shape[1]}) during handling of class weights. The size is expected to be >= 1.`)}else throw new Error(`Unexpected rank of target (y) tensor (${n.rank}) during handling of class weights. The rank is expected to be 1 or 2.`)}),o=Array.from(await r.data());dt(r);const i=[];return o.forEach(a=>{if(e[a]==null)throw new Error(`classWeight must contain all classes in the training data. The class ${a} exists in the data but not in classWeight`);i.push(e[a])}),ke(i,"float32")}else return null}function Sv(n,t){return D(n,t)}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */const vv=32;function tf(n,t){let e,s;const r=t;e=r.xs,s=r.ys,v(e!=null&&s!=null,()=>`A Dataset iterator for fitDataset() is expected to generate objects of the form \`{xs: xVal, ys: yVal}\`, where the two values may be \`tf.Tensor\`, an array of Tensors, or a map of string to Tensor.  The provided Dataset instead generates ${t}`);const o=ef("input",n.inputNames,e),i=ef("output",n.outputNames,s),a=o[0].shape[0];v(o.length===n.inputs.length,()=>`LayersModel has ${n.inputs.length} inputs, but the dataset provides ${o.length} inputs.  (Expected input keys: ${JSON.stringify(n.inputNames)})`),v(i.length===n.outputs.length,()=>`LayersModel has ${n.outputs.length} outputs, but the dataset provides ${i.length} outputs.  (Expected output keys: ${JSON.stringify(n.outputNames)})`);for(let l=0;l<o.length;l++)v(o[l].shape[0]===a,()=>`Batch size mismatch: input ${n.inputNames[l]} has ${o[l].shape[0]}; expected  ${a} based on input ${n.inputNames[0]}.`);for(let l=0;l<i.length;l++)v(i[l].shape[0]===a,()=>`Batch size mismatch: output ${n.outputNames[l]} has ${i[l].shape[0]}; expected  ${a} based on input ${n.inputNames[0]}.`);return{xs:o,ys:i}}function ef(n,t,e){if(e instanceof ee)return[e];if(Array.isArray(e))return v(e.length===t.length,()=>`Received an array of ${e.length} Tensors, but expected ${t.length} to match the ${n} keys ${t}.`),e;{const s=[];for(const r of t){if(e[r]==null)throw new A(`The feature data generated by the dataset lacks the required ${n} key '${r}'.`);s.push(e[r])}return s}}function Nv(n){if(n.length===3)throw new ut("Validation with sample weights is not implemented yet.");return{xs:n[0],ys:n[1]}}async function $v(n,t,e){const s=e.batchesPerEpoch!=null;if(v(n.optimizer!=null,()=>"You must compile a model before training/testing. Use LayersModel.compile(modelCompileConfig)."),v(e!=null,()=>"For fitDataset(), the 2nd argument (config) is required, but it is not provided in this call."),v(e.epochs!=null&&e.epochs>0&&Number.isInteger(e.epochs),()=>`For fitDataset(), config.epochs is expected to be a positive integer, but got ${e.epochs}`),v(!s||e.batchesPerEpoch>0&&Number.isInteger(e.batchesPerEpoch),()=>`For fitDataset(), config.batchesPerEpoch is expected to be a positive integer if specified, but got ${e.batchesPerEpoch}`),v(e.validationSplit==null,()=>"`validationSplit` is not supported by `fitDataset()`. Use validationData instead."),n.isTraining)throw new Error("Cannot start training because another fit() call is ongoing.");n.isTraining=!0;try{const r=e.validationData!=null;let o,i;if(r)if(nf(e.validationData))v(e.validationBatches==null||e.validationBatches>0&&Number.isInteger(e.validationBatches),()=>`For fitDataset() with dataset-based validation, config.validationBatches is expected not to be provided, or to be a positive integer, but got ${e.validationBatches}`);else{const m=Nv(e.validationData);o=m.xs,i=m.ys}const a=n.makeTrainFunction(),l=n.getDedupedMetricsNames();let c;r?c=l.slice().concat(l.map(m=>"val_"+m)):c=l.slice();const u=Wd(e.callbacks,e.yieldEvery),h=e.verbose==null?1:e.verbose,{callbackList:d,history:f}=Vd(u,h,e.epochs,null,null,Tv(t,e),null,r,c);d.setModel(n),n.history=f,await d.onTrainBegin(),n.stopTraining_=!1;let p=e.initialEpoch==null?0:e.initialEpoch,g=await t.iterator();for(;p<e.epochs;){const m={};await d.onEpochBegin(p);let b=0,y=0;for(s||(g=await t.iterator());!s||b<e.batchesPerEpoch;){const k=await g.next();if(s&&k.done){console.warn(`You provided \`batchesPerEpoch\` as ${e.batchesPerEpoch}, but your dataset iterator ran out of data after ${b} batches; interrupting training. Make sure that your dataset can generate at least \`batchesPerEpoch * epochs\` batches (in this case, ${e.batchesPerEpoch*e.epochs} batches). You may need to use the repeat() function when building your dataset.`);break}if(k.value!=null){const{xs:w,ys:I}=tf(n,k.value),S={};S.batch=y,S.size=w[0].shape[0],await d.onBatchBegin(y,S);const T=[];if(e.classWeight!=null){const $=Yd(e.classWeight,n.outputNames);for(let x=0;x<$.length;++x)T.push(await Qd(I[x],null,$[x]))}const C=w.concat(I).concat(T),N=a(C);dt(C);for(let $=0;$<l.length;++$){const x=l[$],F=N[$];S[x]=F,Ke(F)}await d.onBatchEnd(y,S),Bd(S),y++,b++}if(s?b>=e.batchesPerEpoch:k.done){if(r){let w;nf(e.validationData)?w=xt(await n.evaluateDataset(e.validationData,{batches:e.validationBatches})):w=xt(n.evaluate(o,i,{batchSize:e.validationBatchSize==null?vv:e.validationBatchSize,verbose:0}));for(let I=0;I<n.metricsNames.length;++I)m[`val_${n.metricsNames[I]}`]=w[I]}break}if(n.stopTraining_)break}if(await d.onEpochEnd(p,m),p++,n.stopTraining_)break}return await d.onTrainEnd(),await n.history.syncData(),n.history}finally{n.isTraining=!1}}function Tv(n,t){let e=null;return t.batchesPerEpoch!=null?e=t.batchesPerEpoch:Number.isFinite(n.size)&&(e=n.size),e}function nf(n){return typeof n.iterator=="function"}function Cv(n){return typeof n.next=="function"}async function Av(n,t,e){e=e||{};const s=e.batches!=null,r=n.testFunction;let o=[];if(e.verbose>0)throw new ut("Verbose mode is not implemented yet.");v(!s||e.batches>0&&Number.isInteger(e.batches),()=>`Test loop expects \`batches\` to be a positive integer, but received ${JSON.stringify(e.batches)}`);const i=Cv(t)?t:await t.iterator();let a=0,l=0;for(;!s||l<e.batches;){const c=await i.next();if(o=z(()=>{if(c.value){const{xs:u,ys:h}=tf(n,c.value),d=u.concat(h),f=z(()=>r(d));if(dt(d),l===0)for(let g=0;g<f.length;++g)o.push(kt(0));const p=d[0].shape[0];for(let g=0;g<f.length;++g){const m=f[g],b=o[g];o[g]=z(()=>X(o[g],D(p,m))),l>0&&dt(b)}dt(f),a+=p,++l}return o}),c.done){s&&console.warn(`Your dataset iterator ran out of data during evaluateDataset(). Interrupting evalution. Make sure that your dataset can generate at least \`batches\` batches (in this case, ${e.batches} batches). You may need to use the repeat() function when building your dataset.`);break}}for(let c=0;c<o.length;++c){const u=o[c];o[c]=rt(o[c],a),dt(u)}return pe(o)}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Jl(n){v(n>0&&Number.isInteger(n),()=>`batchSize is required to be a positive integer, but got ${n}`)}function gr(n,t,e){return n==null?[null]:Array.isArray(n)?n.map(s=>is(s,t,e-t)):is(n,t,e-t)}function Yl(n,t){return z(()=>n==null?null:Array.isArray(n)?n.map(e=>Yl(e,t)):hd(n,t.dtype==="int32"?t:Q(t,"int32")))}function Ql(n,t){const e=[];let s=0,r=null;for(;s<n;)r=s+t,r>=n&&(r=n),e.push([s,r]),s=r;return e}function sf(n){const t=[];n instanceof ee&&(n=[n]);for(let e=0;e<n.length;++e){const s=n[e];if(s.rank===1)t.push(lr(s,1));else{if(s.rank===0)throw new Error("Expected tensor to be at least 1D, but received a 0D tensor (scalar).");t.push(s)}}return t}function Ue(n,t){if(n==null)return;const e=[];if(t instanceof ee)e.push(t.id);else if(Array.isArray(t))t.forEach(r=>e.push(r.id));else if(t!=null)for(const r in t){const o=t[r];e.push(o.id)}const s=[];if(n instanceof ee)e.indexOf(n.id)===-1&&s.push(n);else if(Array.isArray(n))n.forEach(r=>{e.indexOf(r.id)===-1&&s.push(r)});else if(n!=null)for(const r in n){const o=n[r];e.indexOf(o.id)===-1&&s.push(o)}s.forEach(r=>{r.isDisposed||r.dispose()})}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Ev(n){return n instanceof ee}function tc(n){return Array.isArray(n)}function rf(n){return!Ev(n)&&!tc(n)}function of(n,t,e,s=!0,r=""){if(t==null||t.length===0){if(n!=null){let i=!1;if(tc(n)&&n.length>0)i=!0;else if(rf(n)){for(const a in n)if(n.hasOwnProperty(a)){i=!0;break}}else i=!0;if(i)throw new A(`Error when checking model ${r} expected no data, but got ${n}`)}return[]}if(n==null)return t.map(i=>null);let o;if(rf(n)){n=n,o=[];for(const i of t){if(n[i]==null)throw new A(`No data provided for "${i}". Need data for each key in: ${t}`);o.push(n[i])}}else if(tc(n)){if(n=n,n.length!==t.length)throw new A(`Error when checking model ${r}: the Array of Tensors that you are passing to your model is not the size the model expected. Expected to see ${t.length} Tensor(s), but instead got the following list of Tensor(s): ${n}`);o=n}else{if(n=n,t.length>1)throw new A(`The model ${r} expects ${t.length} Tensor(s), but only received one Tensor. Found: Tensor with shape ${n.shape}`);o=[n]}if(o=sf(o),e!=null)for(let i=0;i<t.length;++i){if(e[i]==null)continue;const a=o[i];if(a.shape.length!==e[i].length)throw new A(`Error when checking ${r}: expected ${t[i]} to have ${e[i].length} dimension(s). but got array with shape ${a.shape}`);for(let l=0;l<e[i].length;++l){if(l===0&&!s)continue;const c=a.shape[l],u=e[i][l];if(u!=null&&u>=0&&c!==u)throw new A(`${r} expected a batch of elements where each example has shape [${e[i].slice(1,e[i].length)}] (i.e.,tensor shape [*,${e[i].slice(1,e[i].length)}]) but the ${r} received an input with ${a.shape[0]} examples, each with shape [${a.shape.slice(1,a.shape.length)}] (tensor shape [${a.shape}])`)}}return o}function Dv(n,t,e){const s=Dn(n.map(o=>o.shape[0]));s.sort();const r=Dn(t.map(o=>o.shape[0]));if(r.sort(),s.length>1)throw new A(`All input Tensors (x) should have the same number of samples. Got array shapes: ${JSON.stringify(n.map(o=>o.shape))}`);if(r.length>1)throw new A(`All target Tensors (y) should have the same number of samples. Got array shapes: ${JSON.stringify(t.map(o=>o.shape))}`);if(s.length>0&&r.length>0&&!oe(s,r))throw new A(`Input Tensors should have the same number of samples as target Tensors. Found ${s[0]} input sample(s) and ${r[0]} target sample(s).`)}function Fv(n,t,e){const s=[Xo,Jo,mr];for(let r=0;r<n.length;++r){const o=n[r],i=t[r],a=e[r];if(i!=null){if(i===mr&&o.shape[o.shape.length-1]===1)throw new A(`You are passing a target array of shape ${o.shape} while using a loss 'categorical_crossentropy'. 'categorical_crossentropy'expects targets to be binary matrices (1s and 0s) of shape [samples, classes].`);if(s.indexOf(i)!==-1){const l=o.shape.slice(1),c=a.slice(1);for(let u=0;u<l.length;++u){const h=l[u],d=c[u];if(d!=null&&h!==d)throw new A(`A target Tensor with shape ${o.shape} was passed for an output of shape ${a}, while using a loss function that expects targets to have the same shape as the output.`)}}}}}function af(n,t,e,s=!0,r=""){let o;if(Array.isArray(n)){if(n.length!==t.length)throw new A(`Error when checking model ${r}: the Array of Tensors that you are passing to your model is not the size the the model expected. Expected to see ${t.length} Tensor(s), but instead got ${n.length} Tensors(s).`);o=n}else{if(t.length>1)throw new A(`The model expects ${t.length} ${r} Tensors, but only received one Tensor. Found: array with shape ${JSON.stringify(n.shape)}.`);o=[n]}if(e!=null)for(let i=0;i<t.length;++i){if(e[i]==null)continue;const a=o[i];if(a.shape.length!==e[i].length)throw new A(`Error when checking ${r}: expected ${t[i]} to have ${e[i].length} dimension(s), but got array with shape ${JSON.stringify(a.shape)}`);for(let l=0;l<e[i].length;++l){if(l===0&&!s)continue;const c=a.shape[l],u=e[i][l];if(u!=null&&u!==c)throw new A(`Error when checking ${r}: expected ${t[i]} to have shape ${JSON.stringify(e[i])} but got array with shape ${JSON.stringify(a.shape)}.`)}}}function Mv(n,t){if(n==null||Array.isArray(n)&&n.length===0)return t.map(s=>[]);let e;if(typeof n=="string"||typeof n=="function")e=[n];else if(Array.isArray(n)||typeof n=="object")e=n;else throw new TypeError(`Type of metrics argument not understood. Expected an string,function, Array, or Object, found: ${n}`);if(Array.isArray(e))return t.map(s=>e);{const s=[];for(const r of t){let o=e.hasOwnProperty(r)?e[r]:[];Array.isArray(o)||(o=[o]),s.push(o)}return s}}const Rv="layers-model";class Rs extends Ge{constructor(t){super(t),this.isTraining=!1}summary(t,e,s=console.log){if(!this.built)throw new A("This model has never been called, thus its weights have not been created yet. So no summary can be displayed. Build the model first (e.g., by calling it on some test data).");gv(this,t,e,s)}compile(t){if(t.loss==null&&(t.loss=[]),this.loss=t.loss,typeof t.optimizer=="string")this.optimizer_=mv(t.optimizer),this.isOptimizerOwned=!0;else{if(!(t.optimizer instanceof En))throw new A("User-defined optimizer must be an instance of tf.Optimizer.");this.optimizer_=t.optimizer,this.isOptimizerOwned=!1}let e=[];if(!Array.isArray(t.loss)&&typeof t.loss!="string"&&typeof t.loss!="function"){t.loss=t.loss;for(const i in t.loss)if(this.outputNames.indexOf(i)===-1)throw new A(`Unknown entry in loss dictionary: "${i}". Only expected the following keys: ${this.outputNames}`);for(const i of this.outputNames)t.loss[i]==null&&console.warn(`Output "${i}" is missing from loss dictionary. We assume this was done on purpose, and we will not be expecting data to be passed to ${i} during training`),e.push(Kl(t.loss[i]))}else if(Array.isArray(t.loss)){if(t.loss.length!==this.outputs.length)throw new A(`When passing an Array as loss, it should have one entry per model output. The model has ${this.outputs.length} output(s), but you passed loss=${t.loss}.`);e=t.loss.map(a=>Kl(a))}else{const i=Kl(t.loss);this.outputs.forEach(a=>{e.push(i)})}this.lossFunctions=e,this.feedOutputNames=[],this.feedOutputShapes=[],this.feedLossFns=[];for(let i=0;i<this.outputs.length;++i){const a=this.internalOutputShapes[i],l=this.outputNames[i];this.feedOutputNames.push(l),this.feedOutputShapes.push(a),this.feedLossFns.push(this.lossFunctions[i])}const s=[];this.metrics=t.metrics,this.metricsNames=["loss"],this.metricsTensors=[],os("loss",()=>{for(let i=0;i<this.outputs.length;++i){if(s.indexOf(i)!==-1)continue;const a=this.lossFunctions[i];this.outputs.length>1&&(this.metricsTensors.push([a,i]),this.metricsNames.push(this.outputNames[i]+"_loss"))}});const r=Mv(t.metrics,this.outputNames),o=(i,a,l)=>{this.outputNames.length>1&&(a=this.outputNames[i]+"_"+a),this.metricsNames.push(a),this.metricsTensors.push([l,i])};os("metric",()=>{for(let i=0;i<this.outputs.length;++i){if(s.indexOf(i)!==-1)continue;const a=r[i];(c=>{let h,d,f;for(const p of c){if(typeof p=="string"&&["accuracy","acc","crossentropy","ce"].indexOf(p)!==-1){const m=this.internalOutputShapes[i];m[m.length-1]===1||this.lossFunctions[i]===Jo?["accuracy","acc"].indexOf(p)!==-1?d=Ud:["crossentropy","ce"].indexOf(p)!==-1&&(d=ov):this.lossFunctions[i]===Zo?["accuracy","acc"].indexOf(p)!==-1?d=iv:["crossentropy","ce"].indexOf(p)!==-1&&(d=jd):["accuracy","acc"].indexOf(p)!==-1?d=Hd:["crossentropy","ce"].indexOf(p)!==-1&&(d=qd);let b;["accuracy","acc"].indexOf(p)!==-1?b="acc":["crossentropy","ce"].indexOf(p)!==-1&&(b="ce"),f=d,h=""+b}else f=pv(p),h=""+ti(p);let g;os(h,()=>{g=f}),o(i,h,g)}})(a)}}),this.collectedTrainableWeights=this.trainableWeights}checkTrainableWeightsConsistency(){this.collectedTrainableWeights!=null&&this.trainableWeights.length!==this.collectedTrainableWeights.length&&console.warn("Discrepancy between trainableweights and collected trainable weights. Did you set `model.trainable` without calling `model.compile()` afterwards?")}evaluate(t,e,s={}){const r=s.batchSize==null?32:s.batchSize;Jl(r);const i=this.standardizeUserDataXY(t,e,!0,r);try{const a=i[0].concat(i[1]);this.makeTestFunction();const l=this.testFunction,c=this.testLoop(l,a,r,s.verbose,s.steps);return pe(c)}finally{Ue(i[0],t),Ue(i[1],e)}}async evaluateDataset(t,e){return this.makeTestFunction(),Av(this,t,e)}checkNumSamples(t,e,s,r="steps"){let o;if(s!=null){if(o=null,e!=null)throw new A(`If ${r} is set, batchSize must be null or undefined.Got batchSize = ${e}`)}else if(t!=null)Array.isArray(t)?o=t[0].shape[0]:o=t.shape[0];else throw new A(`Either the input data should have a defined shape, or ${r} shoud be specified.`);return o}execute(t,e){if(Array.isArray(e)&&e.length===0)throw new A("`outputs` is an empty Array, which is not allowed.");const s=Array.isArray(e),r=s?e:[e],o=this.retrieveSymbolicTensors(r),i=new Rn;if(t instanceof ee&&(t=[t]),Array.isArray(t)){if(t.length!==this.inputs.length)throw new A(`The number of inputs provided (${t.length}) does not match the number of inputs of this model (${this.inputs.length}).`);for(let l=0;l<this.inputs.length;++l)i.add(this.inputs[l],t[l])}else for(const l of this.inputs){const c=t[l.name];if(c==null)throw new A(`No value is provided for the model's input ${l.name}`);i.add(l,c)}const a=dr(o,i);return s?a:a[0]}retrieveSymbolicTensors(t){const e=ns(null,t.length);let s=t.length;for(const r of this.layers){const o=Array.isArray(r.output)?r.output:[r.output],i=o.map(a=>a.name);for(let a=0;a<t.length;++a){const l=i.indexOf(t[a]);if(l!==-1&&(e[a]=o[l],s--),s===0)break}if(s===0)break}if(s>0){const r=[];throw e.forEach((o,i)=>{o==null&&r.push(t[i])}),new A(`Cannot find SymbolicTensors for output name(s): ${JSON.stringify(r)}`)}return e}predictLoop(t,e=32,s=!1){return z(()=>{const r=this.checkNumSamples(t);if(s)throw new ut("Verbose predictLoop() is not implemented yet.");const o=Ql(r,e),i=this.outputs.map(a=>[]);for(let a=0;a<o.length;++a)z(()=>{const c=o[a][0],u=o[a][1],h=gr(t,c,u),d=[];if(Array.isArray(h))for(let p=0;p<h.length;++p)d.push({key:this.inputs[p],value:h[p]});else d.push({key:this.inputs[0],value:h});const f=new Rn(d);return dr(this.outputs,f)}).forEach((c,u)=>i[u].push(c));return pe(i.map(a=>_e(a,0)))})}predict(t,e={}){const s=sf(t);af(s,this.inputNames,this.feedInputShapes,!1);try{const r=e.batchSize==null?32:e.batchSize;return Jl(r),this.predictLoop(s,r)}finally{Ue(s,t)}}predictOnBatch(t){af(t,this.inputNames,this.feedInputShapes,!0);const e=(Array.isArray(t)?t[0]:t).shape[0];return this.predictLoop(t,e)}standardizeUserDataXY(t,e,s=!0,r){if(this.optimizer_==null)throw new De("You must compile a model before training/testing. Use LayersModel.compile(modelCompileArgs).");const o=[];for(let i=0;i<this.feedOutputShapes.length;++i){const a=this.feedOutputShapes[i];this.feedLossFns[i]===Zo?o.push(a.slice(0,a.length-1).concat([1])):o.push(a)}if(t=of(t,this.feedInputNames,this.feedInputShapes,!1,"input"),e=of(e,this.feedOutputNames,o,!1,"target"),Dv(t,e),Fv(e,this.feedLossFns,this.feedOutputShapes),this.stateful&&r!=null&&r>0&&t[0].shape[0]%r!==0)throw new A(`In a stateful network, you should only pass inputs with a number of samples that is divisible by the batch size ${r}. Found: ${t[0].shape[0]} sample(s).`);return[t,e]}async standardizeUserData(t,e,s,r,o=!0,i){const[a,l]=this.standardizeUserDataXY(t,e,o,i);if(s!=null)throw new Error("sample weight is not supported yet.");let c=null;if(r!=null){const u=Yd(r,this.outputNames);c=[];for(let h=0;h<u.length;++h)c.push(await Qd(l[h],null,u[h]))}return[a,l,c]}testLoop(t,e,s,r=0,o){return z(()=>{const i=this.checkNumSamples(e,s,o,"steps"),a=[];if(r>0)throw new ut("Verbose mode is not implemented yet.");if(o!=null)throw new ut("steps mode in testLoop() is not implemented yet");{const l=Ql(i,s),c=ke(Pe(0,i));for(let u=0;u<l.length;++u){const h=l[u][0],d=l[u][1],f=is(c,h,d-h),p=Yl(e,f),g=t(p);if(u===0)for(let m=0;m<g.length;++m)a.push(kt(0));for(let m=0;m<g.length;++m){const b=g[m];a[m]=X(a[m],D(d-h,b))}}for(let u=0;u<a.length;++u)a[u]=rt(a[u],i)}return a})}getDedupedMetricsNames(){const t=this.metricsNames,e=[];for(let s=0;s<t.length;++s){const r=t[s];let o=r;if(ed(t,r)>1){const i=ed(t.slice(0,s),r);o+=`_${i}`}e.push(o)}return e}makeTrainFunction(){return t=>{const e=[],s=t.slice(0,this.inputs.length),r=t.slice(this.inputs.length,this.inputs.length+this.outputs.length),o=t.slice(this.inputs.length+this.outputs.length,this.inputs.length+this.outputs.length*2),i=[],a=()=>{const h=[];for(let g=0;g<this.inputs.length;++g)h.push({key:this.inputs[g],value:s[g]});const d=new Rn(h),f=dr(this.outputs,d,{training:!0});let p;for(let g=0;g<this.lossFunctions.length;++g){const m=this.lossFunctions[g];let b=m(r[g],f[g]);o[g]!=null&&(b=Sv(b,o[g]));const y=Ut(b);e.push(y),g===0?p=b:p=X(p,b)}for(let g=0;g<this.metricsTensors.length;++g){let m;if(this.outputs.length>1&&g<this.outputs.length)m=e[g];else{const b=this.metricsTensors[g][0],y=this.metricsTensors[g][1];m=Ut(b(r[y],f[y]))}Ke(m),i.push(m)}return p=Ut(p),this.calculateLosses().forEach(g=>{p=X(p,g)}),p},l=this.collectedTrainableWeights.map(h=>h.read());return[this.optimizer_.minimize(a,!0,l)].concat(i)}}makeTestFunction(){this.testFunction=t=>z(()=>{const e=[];let s;const r=t.slice(0,this.inputs.length),o=t.slice(this.inputs.length,this.inputs.length+this.outputs.length),i=[];for(let c=0;c<this.inputs.length;++c)i.push({key:this.inputs[c],value:r[c]});const a=new Rn(i),l=dr(this.outputs,a);for(let c=0;c<this.lossFunctions.length;++c){const u=this.lossFunctions[c],h=Ut(u(o[c],l[c]));c===0?s=h:s=X(s,h),e.push(s)}for(let c=0;c<this.metricsTensors.length;++c){const u=this.metricsTensors[c][0],h=this.metricsTensors[c][1],d=Ut(u(o[h],l[h]));e.push(d)}return e})}async fit(t,e,s={}){if(this.isTraining)throw new Error("Cannot start training because another fit() call is ongoing.");this.isTraining=!0;let r,o,i,a,l,c,u,h,d;try{const f=s.batchSize==null?32:s.batchSize;Jl(f);const g=await this.standardizeUserData(t,e,s.sampleWeight,s.classWeight,!1,f);r=g[0],o=g[1],d=g[2];let m=!1,b;if(s.validationData!=null&&s.validationData.length>0){if(m=!0,s.validationData.length===2)l=s.validationData[0],c=s.validationData[1];else throw s.validationData.length===3?new ut("validationData including sample weights is not supported yet."):new A(`When passing validation data, it must contain 2 (valX, valY) or 3 (valX, valY, valSampleWeight) items; ${s.validationData} is invalid.`);const $=await this.standardizeUserData(l,c,null,null,!0,f);u=$[0],h=$[1],b=u.concat(h)}else if(s.validationSplit!=null&&s.validationSplit>0&&s.validationSplit<1){m=!0;const N=Math.floor(r[0].shape[0]*(1-s.validationSplit)),$=r[0].shape[0];u=gr(r,N,$),i=r,r=gr(r,0,N),h=gr(o,N,$),a=o,o=gr(o,0,N),b=u.concat(h)}else s.validationSteps!=null&&(m=!0);const y=r.concat(o).concat(d);this.checkTrainableWeightsConsistency();const k=this.makeTrainFunction(),w=this.getDedupedMetricsNames();let I,S;m?(this.makeTestFunction(),I=this.testFunction,S=w.slice().concat(w.map(N=>"val_"+N))):(I=null,b=[],S=w.slice());const T=Wd(s.callbacks,s.yieldEvery);return await this.fitLoop(k,y,w,f,s.epochs,s.verbose,T,I,b,s.shuffle,S,s.initialEpoch,null,null)}finally{this.isTraining=!1,Ue(r,t),Ue(o,e),Ue(i,t),Ue(a,e),Ue(u,l),Ue(h,c),d!=null&&dt(d)}}async fitLoop(t,e,s,r,o,i,a,l,c,u,h,d,f,p){r==null&&(r=32),o==null&&(o=1),u==null&&(u=!0),d==null&&(d=0);let g=!1;if(l!=null&&c!=null&&(g=!0),p!=null&&(g=!0,f==null))throw new A("Can only use `validationSteps` when doing step-wise training, i.e., `stepsPerEpoch` must be set.");const m=this.checkNumSamples(e,r,f,"steps_per_epoch");let b;m!=null&&(b=Pe(0,m)),i==null&&(i=1);const{callbackList:y,history:k}=Vd(a,i,o,d,m,f,r,g,h);y.setModel(this),this.history=k,await y.onTrainBegin(),this.stopTraining_=!1;for(let w=d;w<o;++w){await y.onEpochBegin(w);const I={};if(f!=null)throw new ut("stepsPerEpoch mode is not implemented yet.");{if(u==="batch")throw new ut("batch shuffling is not implemneted yet");u&&$m(b);const S=ke(b),T=Ql(m,r);for(let C=0;C<T.length;++C){const N={};if(await y.onBatchBegin(C,N),z(()=>{const $=T[C][0],x=T[C][1],F=is(S,$,x-$);N.batch=C,N.size=x-$;const M=Yl(e,F),O=t(M);for(let L=0;L<s.length;++L){const B=s[L],G=O[L];N[B]=G,Ke(G)}if(C===T.length-1&&g){const L=this.testLoop(l,c,r);for(let B=0;B<s.length;++B){const G=s[B],W=L[B];Ke(W),I["val_"+G]=W}}}),await y.onBatchEnd(C,N),Bd(N),this.stopTraining_)break}S.dispose()}if(await y.onEpochEnd(w,I),this.stopTraining_)break}return await y.onTrainEnd(),await this.history.syncData(),this.history}async fitDataset(t,e){return $v(this,t,e)}async trainOnBatch(t,e){const s=await this.standardizeUserData(t,e),r=s[0],o=s[1],a=this.makeTrainFunction()(r.concat(o)),l=[];for(const c of a){const u=await c.data();l.push(u[0])}return dt(a),Ue(s[0],t),Ue(s[1],e),pe(l)}getNamedWeights(t){const e=[],s=t!=null&&t.trainableOnly,r=s?this.trainableWeights:this.weights,o=this.getWeights(s);for(let i=0;i<r.length;++i)s&&!r[i].trainable||e.push({name:r[i].originalName,tensor:o[i]});return e}set stopTraining(t){this.stopTraining_=t}get stopTraining(){return this.stopTraining_}get optimizer(){return this.optimizer_}set optimizer(t){this.optimizer_!==t&&(this.optimizer_=t,this.isOptimizerOwned=!1)}dispose(){const t=super.dispose();if(t.refCountAfterDispose===0&&this.optimizer!=null&&this.isOptimizerOwned){const e=Bu().numTensors;this.optimizer_.dispose(),t.numDisposedVariables+=e-Bu().numTensors}return t}getLossIdentifiers(){let t;if(typeof this.loss=="string")t=yn(this.loss);else if(Array.isArray(this.loss)){for(const e of this.loss)if(typeof e!="string")throw new Error("Serialization of non-string loss is not supported.");t=this.loss.map(e=>yn(e))}else{const e=Object.keys(this.loss);t={};const s=this.loss;for(const r of e)if(typeof s[r]=="string")t[r]=yn(s[r]);else throw new Error("Serialization of non-string loss is not supported.")}return t}getMetricIdentifiers(){if(typeof this.metrics=="string"||typeof this.metrics=="function")return[yn(ti(this.metrics))];if(Array.isArray(this.metrics))return this.metrics.map(t=>yn(ti(t)));{const t={};for(const e in this.metrics)t[e]=yn(ti(this.metrics[e]));return t}}getTrainingConfig(){return{loss:this.getLossIdentifiers(),metrics:this.getMetricIdentifiers(),optimizer_config:{class_name:this.optimizer.getClassName(),config:this.optimizer.getConfig()}}}loadTrainingConfig(t){if(t.weighted_metrics!=null)throw new Error("Loading weight_metrics is not supported yet.");if(t.loss_weights!=null)throw new Error("Loading loss_weights is not supported yet.");if(t.sample_weight_mode!=null)throw new Error("Loading sample_weight_mode is not supported yet.");const e=ni(t.optimizer_config),s=cn(e);let r;if(typeof t.loss=="string")r=ss(t.loss);else if(Array.isArray(t.loss))r=t.loss.map(i=>ss(i));else if(t.loss!=null){r={};for(const i in t.loss)r[i]=ss(t.loss[i])}let o;if(Array.isArray(t.metrics))o=t.metrics.map(i=>ss(i));else if(t.metrics!=null){o={};for(const i in t.metrics)o[i]=ss(t.metrics[i])}this.compile({loss:r,metrics:o,optimizer:s})}async save(t,e){if(typeof t=="string"){const c=ub(t);if(c.length===0)throw new A(`Cannot find any save handlers for URL '${t}'`);if(c.length>1)throw new A(`Found more than one (${c.length}) save handlers for URL '${t}'`);t=c[0]}if(t.save==null)throw new A("LayersModel.save() cannot proceed because the IOHandler provided does not have the `save` attribute defined.");const s=await Pu(this.getNamedWeights(e)),a={modelTopology:this.toJSON(null,!1),format:Rv,generatedBy:`TensorFlow.js tfjs-layers v${Jd}`,convertedBy:null};if((e==null?!1:e.includeOptimizer)&&this.optimizer!=null){a.trainingConfig=this.getTrainingConfig();const c="optimizer",{data:u,specs:h}=await Pu(await this.optimizer.getWeights(),c);s.specs.push(...h),s.data=nb([s.data,u])}return this.userDefinedMetadata!=null&&(Xd(this.userDefinedMetadata,this.name,!0),a.userDefinedMetadata=this.userDefinedMetadata),a.weightData=s.data,a.weightSpecs=s.specs,t.save(a)}setUserDefinedMetadata(t){Xd(t,this.name),this.userDefinedMetadata=t}getUserDefinedMetadata(){return this.userDefinedMetadata}}Rs.className="Model",H(Rs);class lf extends Rs{}lf.className="Functional",H(lf);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */async function zv(n,t){if(t==null&&(t={}),typeof n=="string"){const e=hb(n,t);if(e.length===0)e.push(nk(n,t));else if(e.length>1)throw new A(`Found more than one (${e.length}) load handlers for URL '${n}'`);n=e[0]}return Lv(n,void 0,t)}async function Lv(n,t,e){if(e==null&&(e={}),n.load==null)throw new A("Cannot proceed with model loading because the IOHandler provided does not have the `load` method implemented.");const s=await n.load();let r=s.modelTopology;r.model_config!=null&&(r=r.model_config);const o=e.strict==null?!0:e.strict,i=s.weightData!=null&&s.weightSpecs!=null&&o,a=cn(ni(r),t,i),l=s.trainingConfig;if(l!=null&&a.loadTrainingConfig(l),s.userDefinedMetadata!=null&&a.setUserDefinedMetadata(s.userDefinedMetadata),s.weightData!=null){if(s.weightSpecs==null)throw new A("LayersModel artifacts contains weight data, but not weight specs. Therefore loading of weights cannot proceed.");const{modelWeights:c,optimizerWeights:u}=Ov(s.weightData,s.weightSpecs);a.loadWeights(c,o),a.optimizer!=null&&u.length>0&&await a.optimizer.setWeights(u),dt(c),dt(u.map(h=>h.tensor))}return a}function Ov(n,t){const e=Zg(n,t),s={},r=[];return t.forEach(o=>{o.group==="optimizer"?r.push({name:o.name,tensor:e[o.name]}):s[o.name]=e[o.name]}),{modelWeights:s,optimizerWeights:r}}class br extends Rs{constructor(t){if(super({inputs:[],outputs:[]}),t=t||{},this.trainable=!0,this.built=!1,this.name=t.name!=null?t.name:Po("sequential_"),t.layers!=null)for(const e of t.layers)this.add(e)}checkShape(t){if(t.inboundNodes[0].outputTensors[0].shape.some(s=>s<0))throw new A(`Negative dimension size caused by adding layer ${t.name} with input shape [${t.inboundNodes[0].inputTensors[0].shape}]`)}add(t){const e=t instanceof br||t instanceof Rs;let s;if(e){if(s=t,s.outputs.length!==1)throw new A("All layers in a Sequential model should have a single output tensor. For multi-output layers, use the functional API.");if(s.inputs.length!==1)throw new A("All layers in a Sequential model should have a single input tensor. For multi-input layers, use the functional API.")}if(this.outputs.length===0){if(t.inboundNodes.length===0){if(t.batchInputShape==null)throw new A("The first layer in a Sequential model must get an `inputShape` or `batchInputShape` argument.");const r=Mx({batchShape:t.batchInputShape,dtype:t.dtype,name:t.name+"_input"});t.apply(r)}if(e)this.outputs=s.outputs,this.inputs=s.inputs;else{if(t.inboundNodes.length!==1)throw new A(`A layer added to a Sequential model must not already be connected somewhere else. LayersModel received layer ${t.name} which has ${t.inboundNodes.length} pre-existing inbound connections.`);if(t.inboundNodes[0].outputTensors.length!==1)throw new A("All layers in a Sequential model should have a single output tensor. For multi-output layers, use the functional API.");this.checkShape(t),this.outputs=[t.inboundNodes[0].outputTensors[0]],this.inputs=Sd(this.outputs[0])}this.inboundNodes=[],new Ho({outboundLayer:this,inboundLayers:[],nodeIndices:[],tensorIndices:[],inputTensors:this.inputs,outputTensors:this.outputs,inputMasks:ns(null,this.inputs.length),outputMasks:[null],inputShapes:this.inputs.map(r=>r.shape),outputShapes:this.outputs[0].shape})}else{const r=t.apply(this.outputs[0]);if(Array.isArray(r))throw new TypeError("All layers in a Sequential model should have a single output tensor. For multi-output layers, use the functional API.");this.checkShape(t),this.outputs=[r],this.inboundNodes[0].outputTensors=this.outputs,this.inboundNodes[0].outputShapes=[this.outputs[0].shape]}this.layers.push(t),this.built=!1}pop(){if(this.layers.length===0)throw new TypeError("There are no layers in the model.");if(this.layers.pop(),this.layers.length===0)this.outputs=[],this.inboundNodes=[],this.outboundNodes=[];else{const t=this.layers.length-1;this.layers[t].outboundNodes=[],this.outputs=[this.layers[t].output],this.inboundNodes[0].outputTensors=this.outputs,this.inboundNodes[0].outputShapes=[this.outputs[0].shape]}}call(t,e){return this.model==null&&this.build(),this.model.call(t,e)}build(t){if(yt(t),this.inputs.length===0||this.outputs.length===0)throw new TypeError("Sequential model cannot be built: model is empty. Add some layers first.");this.model=new Rs({inputs:this.inputs,outputs:this.outputs[0],name:this.name+"_model"}),this.model.trainable=this.trainable,this.supportsMasking=this.model.supportsMasking,this.inputLayers=this.model.inputLayers,this.inputLayersNodeIndices=this.model.inputLayersNodeIndices,this.inputLayersTensorIndices=this.model.inputLayersTensorIndices,this.outputLayers=this.model.outputLayers,this.outputLayersNodeIndices=this.model.outputLayersNodeIndices,this.outputLayersTensorIndices=this.model.outputLayersTensorIndices,this.nodesByDepth=this.model.nodesByDepth,this.containerNodes=this.model.containerNodes,this.outputNames=this.model.outputNames,this.inputNames=this.model.inputNames,this.built=!0}countParams(){return this.built||this.build(),super.countParams()}summary(t,e,s=console.log){this.built||this.build(),super.summary(t,e,s)}setWeights(t){this.model==null&&this.build(),this.model.setWeights(t)}evaluate(t,e,s={}){if(!this.built)throw new De("The model needs to be compiled before being used.");return this.model.evaluate(t,e,s)}async evaluateDataset(t,e){if(!this.built)throw new De("The model needs to be compiled before being used.");return this.model.evaluateDataset(t,e)}predict(t,e={}){return this.model==null&&this.build(),this.model.predict(t,e)}predictOnBatch(t){return this.model==null&&this.build(),this.model.predictOnBatch(t)}compile(t){this.build(),this.model.compile(t),this.optimizer_=this.model.optimizer,this.isOptimizerOwned=this.model.isOptimizerOwned,this.loss=this.model.loss,this.metrics=this.model.metrics,this.metricsTensors=this.model.metricsTensors,this.metricsNames=this.model.metricsNames}get optimizer(){return this.model==null?void 0:this.model.optimizer}set optimizer(t){this.model.optimizer=t}async fit(t,e,s={}){if(!this.built)throw new De("The model needs to be compiled before being used.");return this.model.fit(t,e,s)}async fitDataset(t,e){if(!this.built)throw new De("The model needs to be compiled before being used.");return this.model.fitDataset(t,e)}async trainOnBatch(t,e){return this.model.trainOnBatch(t,e)}static fromConfig(t,e,s={},r=!1){let o,i={};if(e instanceof Array){if(e[0].className==null||e[0].className==="Merge")throw new A("Legacy serialization format not supported yet.");o=e}else v(e.layers!=null,()=>"When the config data for a Sequential model is not an Array, it must be an Object that contains the 'layers' field."),o=e.layers,delete e.layers,i=e;const a=new t(i);if(!(a instanceof br))throw new ut(`Sequential.fromConfig called on non-Sequential input: ${a}`);for(const l of o){const u=cn(l,void 0,r);r&&u.setFastWeightInitDuringBuild(!0),a.add(u)}return a}set stopTraining(t){if(this.model==null)throw new A("Cannot set the stopTraining property of a sequential model before it is compiled.");this.model.stopTraining=t}get stopTraining(){if(this.model==null)throw new A("Cannot get the stopTraining property of a sequential model before it is compiled.");return this.model.stopTraining}getConfig(){const t=[];for(const e of this.layers){const s={};s.className=e.getClassName(),s.config=e.getConfig(),t.push(s)}return{name:this.name,layers:t}}}br.className="Sequential",H(br);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */let le=class extends As{getConfig(){return{}}};class cf extends le{apply(t,e=1){return bx(t,e)}}cf.className="elu",H(cf);class uf extends le{apply(t){return Sw(t)}}uf.className="selu",H(uf);class hf extends le{apply(t){return $s(t)}}hf.className="relu",H(hf);class df extends le{apply(t){return z(()=>No(6,$s(t)))}}df.className="relu6",H(df);class ff extends le{apply(t){return t}}ff.className="linear",H(ff);class pf extends le{apply(t){return xo(t)}}pf.className="sigmoid",H(pf);class mf extends le{apply(t){return wx(t)}}mf.className="hardSigmoid",H(mf);class gf extends le{apply(t){return hl(t)}}gf.className="softplus",H(gf);class bf extends le{apply(t){return yx(t)}}bf.className="softsign",H(bf);class yf extends le{apply(t){return rl(t)}}yf.className="tanh",H(yf);let ec=class extends le{apply(t,e=-1){return xh(t,e)}};ec.className="softmax",H(ec);class wf extends le{apply(t,e=-1){return I0(t,e)}}wf.className="logSoftmax",H(wf);class kf extends le{apply(t){return z(()=>z(()=>{const e=Math.sqrt(2),s=D(.5,X(1,qy(rt(t,e))));return D(t,s)}))}}kf.className="gelu",H(kf);class xf extends le{apply(t){return z(()=>D(.5,D(t,X(1,rl(D(ue(rt(2,Math.PI)),X(t,D(.044715,Ss(t,3)))))))))}}xf.className="gelu_new",H(xf);class If extends le{apply(t){return z(()=>D(t,rl(hl(t))))}}If.className="mish",H(If);class Sf extends le{apply(t,e=1){return z(()=>D(xo(D(t,e)),t))}}Sf.className="swish",H(Sf);function zn(n){return n.getClassName()}function nc(n,t={}){return ir(n,Ee.getMap().classNameMap,t,"activation")}function Ln(n){if(n==null){const t={};return t.className="linear",t.config={},nc(t)}if(typeof n=="string"){const t={};return t.className=n,t.config={},nc(t)}else return n instanceof le?n:nc(n)}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function _v(n){if(n!=null&&typeof n!="object")throw new Error(`Argument to L1L2 regularizer's constructor is expected to be an object, but received: ${n}`)}class vf extends As{}class Nf extends vf{constructor(t){super(),_v(t),this.l1=t==null||t.l1==null?.01:t.l1,this.l2=t==null||t.l2==null?.01:t.l2,this.hasL1=this.l1!==0,this.hasL2=this.l2!==0}apply(t){return z(()=>{let e=ae([1]);return this.hasL1&&(e=X(e,st(D(this.l1,fe(t))))),this.hasL2&&(e=X(e,st(D(this.l2,cr(t))))),_(e,[])})}getConfig(){return{l1:this.l1,l2:this.l2}}static fromConfig(t,e){return new t({l1:e.l1,l2:e.l2})}}Nf.className="L1L2",H(Nf);const $f={l1l2:"L1L2"};function Nt(n){return Tl(n)}function Tf(n,t={}){return ir(n,Ee.getMap().classNameMap,t,"regularizer")}function zt(n){if(n==null)return null;if(typeof n=="string"){const e={className:n in $f?$f[n]:n,config:{}};return Tf(e)}else return n instanceof vf?n:Tf(n)}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class Cf extends pt{constructor(t){super(t??{}),this.supportsMasking=!0,t!=null&&(this.maxValue=t.maxValue)}call(t,e){t=ct(t);let s=$s(t);return this.maxValue!=null&&(s=$e(s,0,this.maxValue)),s}computeOutputShape(t){return t}getConfig(){const t={maxValue:this.maxValue},e=super.getConfig();return Object.assign(t,e),t}}Cf.className="ReLU",H(Cf);class Af extends pt{constructor(t){super(t??{}),this.DEFAULT_ALPHA=.3,t==null&&(t={}),this.alpha=t.alpha==null?this.DEFAULT_ALPHA:t.alpha}call(t,e){const s=ct(t);return lh(s,this.alpha)}computeOutputShape(t){return t}getConfig(){const t={alpha:this.alpha},e=super.getConfig();return Object.assign(t,e),t}}Af.className="LeakyReLU",H(Af);class Ef extends pt{constructor(t){if(super(t??{}),this.DEFAULT_ALPHA_INITIALIZER="zeros",t==null&&(t={}),this.supportsMasking=!0,this.alphaInitializer=Rt(t.alphaInitializer||this.DEFAULT_ALPHA_INITIALIZER),this.alphaRegularizer=zt(t.alphaRegularizer),this.alphaConstraint=Kt(t.alphaConstraint),t.sharedAxes==null)this.sharedAxes=null;else if(Array.isArray(t.sharedAxes))this.sharedAxes=t.sharedAxes;else if(typeof t.sharedAxes=="number")this.sharedAxes=[t.sharedAxes];else throw new A(`Expected sharedAxes to be a number or an array of numbers, but got ${t.sharedAxes}`)}build(t){t=yt(t);const e=t.slice(1);if(this.sharedAxes!=null)for(const r of this.sharedAxes)e[r-1]=1;this.alpha=this.addWeight("alpha",e,"float32",this.alphaInitializer,this.alphaRegularizer,!0,this.alphaConstraint);const s={};if(this.sharedAxes!=null)for(let r=1;r<t.length;++r)s[r]=t[r];this.inputSpec=[new qt({ndim:t.length,axes:s})],this.built=!0}call(t,e){return t=ct(t),uh(t,this.alpha.read())}getConfig(){const t={alphaInitializer:Ot(this.alphaInitializer),alphaRegularizer:Nt(this.alphaRegularizer),alphaConstraint:jt(this.alphaConstraint),sharedAxes:this.sharedAxes},e=super.getConfig();return Object.assign(t,e),t}}Ef.className="PReLU",H(Ef);class Df extends pt{constructor(t){if(super(t??{}),this.DEFAULT_ALPHA=1,t==null&&(t={}),t.alpha!=null&&t.alpha!==this.DEFAULT_ALPHA)throw new ut(`Non-default alpha value (${t.alpha}) is not supported by the ELU layer yet.`);this.alpha=t.alpha==null?this.DEFAULT_ALPHA:t.alpha}call(t,e){const s=ct(t);return al(s)}computeOutputShape(t){return t}getConfig(){const t={alpha:this.alpha},e=super.getConfig();return Object.assign(t,e),t}}Df.className="ELU",H(Df);class Ff extends pt{constructor(t){super(t??{}),this.DEFAULT_THETA=1,t==null&&(t={}),this.theta=t.theta==null?this.DEFAULT_THETA:t.theta}call(t,e){const s=ct(t);return D(s,Q(Ae(s,this.theta),"float32"))}computeOutputShape(t){return t}getConfig(){const t={theta:this.theta},e=super.getConfig();return Object.assign(t,e),t}}Ff.className="ThresholdedReLU",H(Ff);class Mf extends pt{constructor(t){super(t??{}),this.DEFAULT_AXIS=1,t==null&&(t={}),this.softmax=new ec().apply,this.axis=t.axis==null?this.DEFAULT_AXIS:t.axis}call(t,e){return z(()=>{let s=ct(t);const r=e.mask;if(r!=null){const o=D(lt(Cn(s.shape),Q(r,s.dtype)),kt(-1e9));s=X(s,o)}return this.axis instanceof Array?this.axis.length>1?mn(lt(s,v0(s,this.axis,!0))):this.softmax(s,this.axis[0]):this.softmax(s,this.axis)})}computeOutputShape(t){return t}getConfig(){const t={axis:this.axis},e=super.getConfig();return Object.assign(t,e),t}}Mf.className="Softmax",H(Mf);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function zs(n,t,e){if(typeof n=="number")return ns(n,t);if(n.length!==t)throw new A(`The ${e} argument must be an integer or tuple of ${t} integers. Received: ${n.length} elements.`);for(let s=0;s<t;++s){const r=n[s];if(!fx(r))throw new A(`The ${e} argument must be an integer or tuple of ${t} integers. Received: ${JSON.stringify(n)} including a non-integer number ${r}`)}return n}function He(n,t,e,s,r=1){if(n==null)return n;const o=t+(t-1)*(r-1);let i;return e==="same"?i=n:i=n-o+1,Math.floor((i+s-1)/s)}function un(n,t,e,s){if(n==null)return null;if(s==="valid")n=n*t+Mn([e-t,0]);else if(s==="same")n=n*t;else throw new A(`Unsupport padding mode: ${s}.`);return n}/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function sc(n,t){return z(()=>(Wt(t),t==="channelsFirst"?bt(n,[0,2,3,1]):n))}function Rf(n,t){return z(()=>(Wt(t),t==="channelsFirst"?bt(n,[0,2,3,4,1]):n))}function Bv(n,t,e,s=1,r="valid",o,i=1){return z(()=>{if(o==null&&(o=We()),Wt(o),n.shape.length!==3)throw new A(`The input of a conv1dWithBias operation should be 3, but is ${n.shape.length} instead.`);if(t.shape.length!==3)throw new A(`The kernel for a conv1dWithBias operation should be 3, but is ${t.shape.length} instead`);if(e!=null&&e.shape.length!==1)throw new A(`The bias for a conv1dWithBias operation should be 1, but is ${e.shape.length} instead`);if(o==="channelsFirst"&&(n=bt(n,[0,2,1])),r==="causal")throw new ut("The support for CAUSAL padding mode in conv1dWithBias is not implemented yet.");let a=Sy(n,t,s,r==="same"?"same":"valid","NWC",i);return e!=null&&(a=Ve(a,e)),a})}function zf(n,t,e,s=[1,1],r="valid",o,i,a=null){return z(()=>{if(o==null&&(o=We()),Wt(o),n.rank!==3&&n.rank!==4)throw new A(`conv2dWithBiasActivation expects input to be of rank 3 or 4, but received ${n.rank}.`);if(t.rank!==3&&t.rank!==4)throw new A(`conv2dWithBiasActivation expects kernel to be of rank 3 or 4, but received ${n.rank}.`);let l=sc(n,o);if(r==="causal")throw new ut("The support for CAUSAL padding mode in conv1dWithBias is not implemented yet.");return l=Jw({x:l,filter:t,strides:s,pad:r==="same"?"same":"valid",dilations:i,dataFormat:"NHWC",bias:e,activation:a}),o==="channelsFirst"&&(l=bt(l,[0,3,1,2])),l})}function Pv(n,t,e,s=[1,1,1],r="valid",o,i){return z(()=>{if(o==null&&(o=We()),Wt(o),n.rank!==4&&n.rank!==5)throw new A(`conv3dWithBias expects input to be of rank 4 or 5, but received ${n.rank}.`);if(t.rank!==4&&t.rank!==5)throw new A(`conv3dWithBias expects kernel to be of rank 4 or 5, but received ${n.rank}.`);let a=Rf(n,o);if(r==="causal")throw new ut("The support for CAUSAL padding mode in conv3dWithBias is not implemented yet.");return a=Cy(a,t,s,r==="same"?"same":"valid","NDHWC",i),e!=null&&(a=Ve(a,e)),o==="channelsFirst"&&(a=bt(a,[0,4,1,2,3])),a})}class si extends pt{constructor(t,e){if(super(e),this.bias=null,this.DEFAULT_KERNEL_INITIALIZER="glorotNormal",this.DEFAULT_BIAS_INITIALIZER="zeros",si.verifyArgs(e),this.rank=t,Qt(this.rank,"rank"),this.rank!==1&&this.rank!==2&&this.rank!==3)throw new ut(`Convolution layer for rank other than 1, 2, or 3 (${this.rank}) is not implemented yet.`);if(this.kernelSize=zs(e.kernelSize,t,"kernelSize"),this.strides=zs(e.strides==null?1:e.strides,t,"strides"),this.padding=e.padding==null?"valid":e.padding,Se(this.padding),this.dataFormat=e.dataFormat==null?"channelsLast":e.dataFormat,Wt(this.dataFormat),this.activation=Ln(e.activation),this.useBias=e.useBias==null?!0:e.useBias,this.biasInitializer=Rt(e.biasInitializer||this.DEFAULT_BIAS_INITIALIZER),this.biasConstraint=Kt(e.biasConstraint),this.biasRegularizer=zt(e.biasRegularizer),this.activityRegularizer=zt(e.activityRegularizer),this.dilationRate=zs(e.dilationRate==null?1:e.dilationRate,t,"dilationRate"),this.rank===1&&Array.isArray(this.dilationRate)&&this.dilationRate.length!==1)throw new A(`dilationRate must be a number or an array of a single number for 1D convolution, but received ${JSON.stringify(this.dilationRate)}`);if(this.rank===2){if(typeof this.dilationRate=="number")this.dilationRate=[this.dilationRate,this.dilationRate];else if(this.dilationRate.length!==2)throw new A(`dilationRate must be a number or array of two numbers for 2D convolution, but received ${JSON.stringify(this.dilationRate)}`)}else if(this.rank===3){if(typeof this.dilationRate=="number")this.dilationRate=[this.dilationRate,this.dilationRate,this.dilationRate];else if(this.dilationRate.length!==3)throw new A(`dilationRate must be a number or array of three numbers for 3D convolution, but received ${JSON.stringify(this.dilationRate)}`)}}static verifyArgs(t){if(rn("kernelSize"in t,"required key 'kernelSize' not in config"),typeof t.kernelSize!="number"&&!Al(t.kernelSize,"number",1,3))throw new A(`BaseConv expects config.kernelSize to be number or number[] with length 1, 2, or 3, but received ${JSON.stringify(t.kernelSize)}.`)}getConfig(){const t={kernelSize:this.kernelSize,strides:this.strides,padding:this.padding,dataFormat:this.dataFormat,dilationRate:this.dilationRate,activation:zn(this.activation),useBias:this.useBias,biasInitializer:Ot(this.biasInitializer),biasRegularizer:Nt(this.biasRegularizer),activityRegularizer:Nt(this.activityRegularizer),biasConstraint:jt(this.biasConstraint)},e=super.getConfig();return Object.assign(t,e),t}}class Ls extends si{constructor(t,e){super(t,e),this.kernel=null,Ls.verifyArgs(e),this.filters=e.filters,Qt(this.filters,"filters"),this.kernelInitializer=Rt(e.kernelInitializer||this.DEFAULT_KERNEL_INITIALIZER),this.kernelConstraint=Kt(e.kernelConstraint),this.kernelRegularizer=zt(e.kernelRegularizer)}build(t){t=yt(t);const e=this.dataFormat==="channelsFirst"?1:t.length-1;if(t[e]==null)throw new A(`The channel dimension of the input should be defined. Found ${t[e]}`);const s=t[e],r=this.kernelSize.concat([s,this.filters]);this.kernel=this.addWeight("kernel",r,null,this.kernelInitializer,this.kernelRegularizer,!0,this.kernelConstraint),this.useBias&&(this.bias=this.addWeight("bias",[this.filters],null,this.biasInitializer,this.biasRegularizer,!0,this.biasConstraint)),this.inputSpec=[{ndim:this.rank+2,axes:{[e]:s}}],this.built=!0}call(t,e){return z(()=>{t=ct(t);let s;const r=this.bias==null?null:this.bias.read(),o=sd(this.activation.getClassName());if(o!=null&&this.rank===2)s=zf(t,this.kernel.read(),r,this.strides,this.padding,this.dataFormat,this.dilationRate,o);else{if(this.rank===1)s=Bv(t,this.kernel.read(),r,this.strides[0],this.padding,this.dataFormat,this.dilationRate[0]);else if(this.rank===2)s=zf(t,this.kernel.read(),r,this.strides,this.padding,this.dataFormat,this.dilationRate);else if(this.rank===3)s=Pv(t,this.kernel.read(),r,this.strides,this.padding,this.dataFormat,this.dilationRate);else throw new ut("convolutions greater than 3D are not implemented yet.");this.activation!=null&&(s=this.activation.apply(s))}return s})}computeOutputShape(t){t=yt(t);const e=[],s=this.dataFormat==="channelsLast"?t.slice(1,t.length-1):t.slice(2);for(let o=0;o<s.length;++o){const i=He(s[o],this.kernelSize[o],this.padding,this.strides[o],typeof this.dilationRate=="number"?this.dilationRate:this.dilationRate[o]);e.push(i)}let r=[t[0]];return this.dataFormat==="channelsLast"?(r=r.concat(e),r.push(this.filters)):(r.push(this.filters),r=r.concat(e)),r}getConfig(){const t={filters:this.filters,kernelInitializer:Ot(this.kernelInitializer),kernelRegularizer:Nt(this.kernelRegularizer),kernelConstraint:jt(this.kernelConstraint)},e=super.getConfig();return Object.assign(t,e),t}static verifyArgs(t){if(!("filters"in t)||typeof t.filters!="number"||t.filters<1)throw new A(`Convolution layer expected config.filters to be a 'number' > 0 but got ${JSON.stringify(t.filters)}`)}}class yr extends Ls{constructor(t){super(2,t),yr.verifyArgs(t)}getConfig(){const t=super.getConfig();return delete t.rank,t}static verifyArgs(t){if(typeof t.kernelSize!="number"&&!Al(t.kernelSize,"number",1,2))throw new A(`Conv2D expects config.kernelSize to be number or number[] with length 1 or 2, but received ${JSON.stringify(t.kernelSize)}.`)}}yr.className="Conv2D",H(yr);class wr extends Ls{constructor(t){super(3,t),wr.verifyArgs(t)}getConfig(){const t=super.getConfig();return delete t.rank,t}static verifyArgs(t){if(typeof t.kernelSize!="number"&&!(Array.isArray(t.kernelSize)&&(t.kernelSize.length===1||t.kernelSize.length===3)))throw new A(`Conv3D expects config.kernelSize to be number or [number, number, number], but received ${JSON.stringify(t.kernelSize)}.`)}}wr.className="Conv3D",H(wr);class Lf extends yr{constructor(t){if(super(t),this.inputSpec=[new qt({ndim:4})],this.padding!=="same"&&this.padding!=="valid")throw new A(`Conv2DTranspose currently supports only padding modes 'same' and 'valid', but received padding mode ${this.padding}`)}build(t){if(t=yt(t),t.length!==4)throw new A("Input should have rank 4; Received input shape: "+JSON.stringify(t));const e=this.dataFormat==="channelsFirst"?1:t.length-1;if(t[e]==null)throw new A("The channel dimension of the inputs should be defined. Found `None`.");const s=t[e],r=this.kernelSize.concat([this.filters,s]);this.kernel=this.addWeight("kernel",r,"float32",this.kernelInitializer,this.kernelRegularizer,!0,this.kernelConstraint),this.useBias&&(this.bias=this.addWeight("bias",[this.filters],"float32",this.biasInitializer,this.biasRegularizer,!0,this.biasConstraint)),this.inputSpec=[new qt({ndim:4,axes:{[e]:s}})],this.built=!0}call(t,e){return z(()=>{let s=ct(t);if(s.shape.length!==4)throw new A(`Conv2DTranspose.call() expects input tensor to be rank-4, but received a tensor of rank-${s.shape.length}`);const r=s.shape,o=r[0];let i,a;this.dataFormat==="channelsFirst"?(i=2,a=3):(i=1,a=2);const l=r[i],c=r[a],u=this.kernelSize[0],h=this.kernelSize[1],d=this.strides[0],f=this.strides[1],p=un(l,d,u,this.padding),g=un(c,f,h,this.padding),m=[o,p,g,this.filters];this.dataFormat!=="channelsLast"&&(s=bt(s,[0,2,3,1]));let b=$y(s,this.kernel.read(),m,this.strides,this.padding);return this.dataFormat!=="channelsLast"&&(b=bt(b,[0,3,1,2])),this.bias!=null&&(b=Ve(b,this.bias.read(),this.dataFormat)),this.activation!=null&&(b=this.activation.apply(b)),b})}computeOutputShape(t){t=yt(t);const e=t.slice();let s,r,o;this.dataFormat==="channelsFirst"?(s=1,r=2,o=3):(s=3,r=1,o=2);const i=this.kernelSize[0],a=this.kernelSize[1],l=this.strides[0],c=this.strides[1];return e[s]=this.filters,e[r]=un(e[r],l,i,this.padding),e[o]=un(e[o],c,a,this.padding),e}getConfig(){const t=super.getConfig();return delete t.dilationRate,t}}Lf.className="Conv2DTranspose",H(Lf);class Of extends wr{constructor(t){if(super(t),this.inputSpec=[new qt({ndim:5})],this.padding!=="same"&&this.padding!=="valid")throw new A(`Conv3DTranspose currently supports only padding modes 'same' and 'valid', but received padding mode ${this.padding}`)}build(t){if(t=yt(t),t.length!==5)throw new A("Input should have rank 5; Received input shape: "+JSON.stringify(t));const e=this.dataFormat==="channelsFirst"?1:t.length-1;if(t[e]==null)throw new A("The channel dimension of the inputs should be defined. Found `None`.");const s=t[e],r=this.kernelSize.concat([this.filters,s]);this.kernel=this.addWeight("kernel",r,"float32",this.kernelInitializer,this.kernelRegularizer,!0,this.kernelConstraint),this.useBias&&(this.bias=this.addWeight("bias",[this.filters],"float32",this.biasInitializer,this.biasRegularizer,!0,this.biasConstraint)),this.inputSpec=[new qt({ndim:5,axes:{[e]:s}})],this.built=!0}call(t,e){return z(()=>{let s=ct(t);if(s.shape.length!==5)throw new A(`Conv3DTranspose.call() expects input tensor to be rank-4, but received a tensor of rank-${s.shape.length}`);const r=s.shape,o=r[0];let i,a,l;this.dataFormat==="channelsFirst"?(l=2,i=3,a=4):(l=1,i=2,a=3);const c=r[l],u=r[i],h=r[a],d=this.kernelSize[0],f=this.kernelSize[1],p=this.kernelSize[2],g=this.strides[0],m=this.strides[1],b=this.strides[2],y=un(c,g,d,this.padding),k=un(u,m,f,this.padding),w=un(h,b,p,this.padding),I=[o,y,k,w,this.filters];this.dataFormat!=="channelsLast"&&(s=bt(s,[0,2,3,4,1]));let S=Dy(s,this.kernel.read(),I,this.strides,this.padding);return this.dataFormat!=="channelsLast"&&(S=bt(S,[0,4,1,2,3])),this.bias!==null&&(S=Ve(S,this.bias.read(),this.dataFormat)),this.activation!==null&&(S=this.activation.apply(S)),S})}computeOutputShape(t){t=yt(t);const e=t.slice();let s,r,o,i;this.dataFormat==="channelsFirst"?(s=1,r=2,o=3,i=4):(s=4,r=1,o=2,i=3);const a=this.kernelSize[0],l=this.kernelSize[1],c=this.kernelSize[2],u=this.strides[0],h=this.strides[1],d=this.strides[2];return e[s]=this.filters,e[r]=un(e[r],u,a,this.padding),e[o]=un(e[o],h,l,this.padding),e[i]=un(e[i],d,c,this.padding),e}getConfig(){const t=super.getConfig();return delete t.dilationRate,t}}Of.className="Conv3DTranspose",H(Of);class _f extends Ls{constructor(t,e){if(super(t,e),this.DEFAULT_DEPTHWISE_INITIALIZER="glorotUniform",this.DEFAULT_POINTWISE_INITIALIZER="glorotUniform",this.depthwiseKernel=null,this.pointwiseKernel=null,e.filters==null)throw new A("The `filters` configuration field is required by SeparableConv, but is unspecified.");if(e.kernelInitializer!=null||e.kernelRegularizer!=null||e.kernelConstraint!=null)throw new A("Fields kernelInitializer, kernelRegularizer and kernelConstraint are invalid for SeparableConv2D. Use depthwiseInitializer, depthwiseRegularizer, depthwiseConstraint, pointwiseInitializer, pointwiseRegularizer and pointwiseConstraint instead.");if(e.padding!=null&&e.padding!=="same"&&e.padding!=="valid")throw new A(`SeparableConv${this.rank}D supports only padding modes: 'same' and 'valid', but received ${JSON.stringify(e.padding)}`);this.depthMultiplier=e.depthMultiplier==null?1:e.depthMultiplier,this.depthwiseInitializer=Rt(e.depthwiseInitializer||this.DEFAULT_DEPTHWISE_INITIALIZER),this.depthwiseRegularizer=zt(e.depthwiseRegularizer),this.depthwiseConstraint=Kt(e.depthwiseConstraint),this.pointwiseInitializer=Rt(e.depthwiseInitializer||this.DEFAULT_POINTWISE_INITIALIZER),this.pointwiseRegularizer=zt(e.pointwiseRegularizer),this.pointwiseConstraint=Kt(e.pointwiseConstraint)}build(t){if(t=yt(t),t.length<this.rank+2)throw new A(`Inputs to SeparableConv${this.rank}D should have rank ${this.rank+2}, but received input shape: ${JSON.stringify(t)}`);const e=this.dataFormat==="channelsFirst"?1:t.length-1;if(t[e]==null||t[e]<0)throw new A(`The channel dimension of the inputs should be defined, but found ${JSON.stringify(t[e])}`);const s=t[e],r=this.kernelSize.concat([s,this.depthMultiplier]),o=[];for(let a=0;a<this.rank;++a)o.push(1);o.push(s*this.depthMultiplier,this.filters);const i=!0;this.depthwiseKernel=this.addWeight("depthwise_kernel",r,"float32",this.depthwiseInitializer,this.depthwiseRegularizer,i,this.depthwiseConstraint),this.pointwiseKernel=this.addWeight("pointwise_kernel",o,"float32",this.pointwiseInitializer,this.pointwiseRegularizer,i,this.pointwiseConstraint),this.useBias?this.bias=this.addWeight("bias",[this.filters],"float32",this.biasInitializer,this.biasRegularizer,i,this.biasConstraint):this.bias=null,this.inputSpec=[new qt({ndim:this.rank+2,axes:{[e]:s}})],this.built=!0}call(t,e){return z(()=>{t=ct(t);let s;if(this.rank===1)throw new ut("1D separable convolution is not implemented yet.");return this.rank===2&&(this.dataFormat==="channelsFirst"&&(t=bt(t,[0,2,3,1])),s=Nw(t,this.depthwiseKernel.read(),this.pointwiseKernel.read(),this.strides,this.padding,this.dilationRate,"NHWC")),this.useBias&&(s=Ve(s,this.bias.read(),this.dataFormat)),this.activation!=null&&(s=this.activation.apply(s)),this.dataFormat==="channelsFirst"&&(s=bt(s,[0,3,1,2])),s})}getConfig(){const t=super.getConfig();return delete t.rank,delete t.kernelInitializer,delete t.kernelRegularizer,delete t.kernelConstraint,t.depthwiseInitializer=Ot(this.depthwiseInitializer),t.pointwiseInitializer=Ot(this.pointwiseInitializer),t.depthwiseRegularizer=Nt(this.depthwiseRegularizer),t.pointwiseRegularizer=Nt(this.pointwiseRegularizer),t.depthwiseConstraint=jt(this.depthwiseConstraint),t.pointwiseConstraint=jt(this.pointwiseConstraint),t}}_f.className="SeparableConv";class Bf extends _f{constructor(t){super(2,t)}}Bf.className="SeparableConv2D",H(Bf);class ri extends Ls{constructor(t){super(1,t),ri.verifyArgs(t),this.inputSpec=[{ndim:3}]}getConfig(){const t=super.getConfig();return delete t.rank,delete t.dataFormat,t}static verifyArgs(t){if(typeof t.kernelSize!="number"&&!Al(t.kernelSize,"number",1,1))throw new A(`Conv1D expects config.kernelSize to be number or number[] with length 1, but received ${JSON.stringify(t.kernelSize)}.`)}}ri.className="Conv1D",H(ri);class Pf extends pt{constructor(t){super(t),typeof t.cropping=="number"?this.cropping=[[t.cropping,t.cropping],[t.cropping,t.cropping]]:typeof t.cropping[0]=="number"?this.cropping=[[t.cropping[0],t.cropping[0]],[t.cropping[1],t.cropping[1]]]:this.cropping=t.cropping,this.dataFormat=t.dataFormat===void 0?"channelsLast":t.dataFormat,this.inputSpec=[{ndim:4}]}computeOutputShape(t){return this.dataFormat==="channelsFirst"?[t[0],t[1],t[2]-this.cropping[0][0]-this.cropping[0][1],t[3]-this.cropping[1][0]-this.cropping[1][1]]:[t[0],t[1]-this.cropping[0][0]-this.cropping[0][1],t[2]-this.cropping[1][0]-this.cropping[1][1],t[3]]}call(t,e){return z(()=>{if(t=ct(t),this.dataFormat==="channelsLast"){const s=Wo(t,this.cropping[0][0],t.shape[1]-this.cropping[0][0]-this.cropping[0][1],2);return Wo(s,this.cropping[1][0],t.shape[2]-this.cropping[1][1]-this.cropping[1][0],3)}else{const s=Wo(t,this.cropping[0][0],t.shape[2]-this.cropping[0][0]-this.cropping[0][1],3);return Wo(s,this.cropping[1][0],t.shape[3]-this.cropping[1][1]-this.cropping[1][0],4)}})}getConfig(){const t={cropping:this.cropping,dataFormat:this.dataFormat},e=super.getConfig();return Object.assign(t,e),t}}Pf.className="Cropping2D",H(Pf);class Wf extends pt{constructor(t){super(t),this.DEFAULT_SIZE=[2,2],this.inputSpec=[{ndim:4}],this.size=t.size==null?this.DEFAULT_SIZE:t.size,this.dataFormat=t.dataFormat==null?"channelsLast":t.dataFormat,Wt(this.dataFormat),this.interpolation=t.interpolation==null?"nearest":t.interpolation,ux(this.interpolation)}computeOutputShape(t){if(this.dataFormat==="channelsFirst"){const e=t[2]==null?null:this.size[0]*t[2],s=t[3]==null?null:this.size[1]*t[3];return[t[0],t[1],e,s]}else{const e=t[1]==null?null:this.size[0]*t[1],s=t[2]==null?null:this.size[1]*t[2];return[t[0],e,s,t[3]]}}call(t,e){return z(()=>{let s=ct(t);const r=s.shape;if(this.dataFormat==="channelsFirst"){s=bt(s,[0,2,3,1]);const o=this.size[0]*r[2],i=this.size[1]*r[3],a=this.interpolation==="nearest"?bn.resizeNearestNeighbor(s,[o,i]):bn.resizeBilinear(s,[o,i]);return bt(a,[0,3,1,2])}else{const o=this.size[0]*r[1],i=this.size[1]*r[2];return this.interpolation==="nearest"?bn.resizeNearestNeighbor(s,[o,i]):bn.resizeBilinear(s,[o,i])}})}getConfig(){const t={size:this.size,dataFormat:this.dataFormat,interpolation:this.interpolation},e=super.getConfig();return Object.assign(t,e),t}}Wf.className="UpSampling2D",H(Wf);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Wv(n,t,e=[1,1],s="valid",r,o){return z(()=>{r==null&&(r=We()),Wt(r);let i=sc(n,r);if(n.rank!==4)throw new A(`Input for depthwiseConv2d is required to be 4-D, but is instead ${n.rank}-D`);if(t.rank!==4)throw new A(`depthwiseKernel is required to be 4-D, but is instead ${t.rank}-D`);return i=nh(i,t,e,s==="same"?"same":"valid","NHWC",o),r==="channelsFirst"&&(i=bt(i,[0,3,1,2])),i})}class Vf extends si{constructor(t){super(2,t),this.depthwiseKernel=null,this.depthMultiplier=t.depthMultiplier==null?1:t.depthMultiplier,this.depthwiseInitializer=Rt(t.depthwiseInitializer||this.DEFAULT_KERNEL_INITIALIZER),this.depthwiseConstraint=Kt(t.depthwiseConstraint),this.depthwiseRegularizer=zt(t.depthwiseRegularizer)}build(t){if(t=yt(t),t.length<4)throw new A(`Inputs to DepthwiseConv2D should have rank 4. Received input shape: ${JSON.stringify(t)}.`);const e=this.dataFormat==="channelsFirst"?1:3;if(t[e]==null||t[e]<0)throw new A(`The channel dimension of the inputs to DepthwiseConv2D should be defined, but is not (${t[e]}).`);const s=t[e],r=[this.kernelSize[0],this.kernelSize[1],s,this.depthMultiplier];this.depthwiseKernel=this.addWeight("depthwise_kernel",r,null,this.depthwiseInitializer,this.depthwiseRegularizer,!0,this.depthwiseConstraint),this.useBias?this.bias=this.addWeight("bias",[s*this.depthMultiplier],null,this.biasInitializer,this.biasRegularizer,!0,this.biasConstraint):this.bias=null,this.built=!0}call(t,e){return z(()=>{t=ct(t);let s=Wv(t,this.depthwiseKernel.read(),this.strides,this.padding,this.dataFormat,null);return this.useBias&&(s=Ve(s,this.bias.read(),this.dataFormat)),this.activation!=null&&(s=this.activation.apply(s)),s})}computeOutputShape(t){t=yt(t);const e=this.dataFormat==="channelsFirst"?t[2]:t[1],s=this.dataFormat==="channelsFirst"?t[3]:t[2],r=this.dataFormat==="channelsFirst"?t[1]*this.depthMultiplier:t[3]*this.depthMultiplier,o=He(e,this.kernelSize[0],this.padding,this.strides[0]),i=He(s,this.kernelSize[1],this.padding,this.strides[1]);return this.dataFormat==="channelsFirst"?[t[0],r,o,i]:[t[0],o,i,r]}getConfig(){const t=super.getConfig();return t.depthMultiplier=this.depthMultiplier,t.depthwiseInitializer=Ot(this.depthwiseInitializer),t.depthwiseRegularizer=Nt(this.depthwiseRegularizer),t.depthwiseConstraint=jt(this.depthwiseRegularizer),t}}Vf.className="DepthwiseConv2D",H(Vf);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Gf(n,t,e,s){if(Array.isArray(n)){if(t!=null||e!=null)throw new A("When inputs is an array, neither initialState or constants should be provided");s!=null&&(e=n.slice(n.length-s,n.length),n=n.slice(0,n.length-s)),n.length>1&&(t=n.slice(1,n.length)),n=n[0]}function r(o){return o==null||Array.isArray(o)?o:[o]}return t=r(t),e=r(e),{inputs:n,initialState:t,constants:e}}function Uf(n,t,e,s=!1,r,o,i=!1,a=!1){return z(()=>{const l=t.shape.length;if(l<3)throw new A(`Input should be at least 3D, but is ${l}D.`);const c=[1,0].concat(Pe(2,l));t=bt(t,c),i&&console.warn("Backend rnn(): the unroll = true option is not applicable to the imperative deeplearn.js backend."),r!=null&&(r=Q(Q(r,"bool"),"float32"),r.rank===l-1&&(r=we(r,-1)),r=bt(r,c)),s&&(t=Mo(t,0),r!=null&&(r=Mo(r,0)));const u=[];let h,d=e;const f=t.shape[0],p=Ts(t);let g;r!=null&&(g=Ts(r));for(let b=0;b<f;++b){const y=p[b],k=z(()=>n(y,d));if(r==null)h=k[0],d=k[1];else{const w=z(()=>{const I=g[b],S=lt(Be(I),I),T=X(D(k[0],I),D(d[0],S)),C=d.map((N,$)=>X(D(k[1][$],I),D(N,S)));return{output:T,newStates:C}});h=w.output,d=w.newStates}a&&u.push(h)}let m;return a&&(m=An(u,1)),[h,m,d]})}class On extends pt{constructor(t){super(t);let e;if(t.cell==null)throw new A("cell property is missing for the constructor of RNN.");if(Array.isArray(t.cell)?e=new ic({cells:t.cell}):e=t.cell,e.stateSize==null)throw new A("The RNN cell should have an attribute `stateSize` (tuple of integers, one integer per RNN state).");this.cell=e,this.returnSequences=t.returnSequences==null?!1:t.returnSequences,this.returnState=t.returnState==null?!1:t.returnState,this.goBackwards=t.goBackwards==null?!1:t.goBackwards,this._stateful=t.stateful==null?!1:t.stateful,this.unroll=t.unroll==null?!1:t.unroll,this.supportsMasking=!0,this.inputSpec=[new qt({ndim:3})],this.stateSpec=null,this.states_=null,this.numConstants=null,this.keptStates=[]}getStates(){if(this.states_==null){const t=Array.isArray(this.cell.stateSize)?this.cell.stateSize.length:1;return Pe(0,t).map(e=>null)}else return this.states_}setStates(t){this.states_=t}computeOutputShape(t){Vl(t)&&(t=t[0]),t=t;let e=this.cell.stateSize;Array.isArray(e)||(e=[e]);const s=e[0];let r;if(this.returnSequences?r=[t[0],t[1],s]:r=[t[0],s],this.returnState){const o=[];for(const i of e)o.push([t[0],i]);return[r].concat(o)}else return r}computeMask(t,e){return z(()=>{Array.isArray(e)&&(e=e[0]);const s=this.returnSequences?e:null;if(this.returnState){const r=this.states.map(o=>null);return[s].concat(r)}else return s})}get states(){if(this.states_==null){const t=Array.isArray(this.cell.stateSize)?this.cell.stateSize.length:1,e=[];for(let s=0;s<t;++s)e.push(null);return e}else return this.states_}set states(t){this.states_=t}build(t){if(this.numConstants!=null)throw new ut("Constants support is not implemented in RNN yet.");Vl(t)&&(t=t[0]),t=t;const e=this.stateful?t[0]:null,s=t.slice(2);this.inputSpec[0]=new qt({shape:[e,null,...s]});const r=[t[0]].concat(t.slice(2));this.cell.build(r);let o;if(Array.isArray(this.cell.stateSize)?o=this.cell.stateSize:o=[this.cell.stateSize],this.stateSpec!=null){if(!oe(this.stateSpec.map(i=>i.shape[i.shape.length-1]),o))throw new A(`An initialState was passed that is not compatible with cell.stateSize. Received stateSpec=${this.stateSpec}; However cell.stateSize is ${this.cell.stateSize}`)}else this.stateSpec=o.map(i=>new qt({shape:[null,i]}));this.stateful&&this.resetStates()}resetStates(t,e=!1){z(()=>{if(!this.stateful)throw new sn("Cannot call resetStates() on an RNN Layer that is not stateful.");const s=this.inputSpec[0].shape[0];if(s==null)throw new A("If an RNN is stateful, it needs to know its batch size. Specify the batch size of your input tensors: \n- If using a Sequential model, specify the batch size by passing a `batchInputShape` option to your first layer.\n- If using the functional API, specify the batch size by passing a `batchShape` option to your Input layer.");if(this.states_==null)Array.isArray(this.cell.stateSize)?this.states_=this.cell.stateSize.map(r=>ae([s,r])):this.states_=[ae([s,this.cell.stateSize])];else if(t==null)dt(this.states_),this.keptStates!=null&&(dt(this.keptStates),this.keptStates=[]),Array.isArray(this.cell.stateSize)?this.states_=this.cell.stateSize.map(r=>ae([s,r])):this.states_[0]=ae([s,this.cell.stateSize]);else{if(Array.isArray(t)||(t=[t]),t.length!==this.states_.length)throw new A(`Layer ${this.name} expects ${this.states_.length} state(s), but it received ${t.length} state value(s). Input received: ${t}`);e===!0?this.keptStates.push(this.states_.slice()):dt(this.states_);for(let r=0;r<this.states_.length;++r){const o=t[r],i=Array.isArray(this.cell.stateSize)?this.cell.stateSize[r]:this.cell.stateSize,a=[s,i];if(!oe(o.shape,a))throw new A(`State ${r} is incompatible with layer ${this.name}: expected shape=${a}, received shape=${o.shape}`);this.states_[r]=o}}this.states_=this.states_.map(r=>Ke(r.clone()))})}apply(t,e){let s=e==null?null:e.initialState,r=e==null?null:e.constants;e==null&&(e={});const o=Gf(t,s,r,this.numConstants);t=o.inputs,s=o.initialState,r=o.constants;let i=[],a=[];if(s!=null){e.initialState=s,i=i.concat(s),this.stateSpec=[];for(const c of s)this.stateSpec.push(new qt({shape:c.shape}));a=a.concat(this.stateSpec)}if(r!=null&&(e.constants=r,i=i.concat(r),this.numConstants=r.length),i[0]instanceof ln){const c=[t].concat(i),u=this.inputSpec.concat(a),h=this.inputSpec;this.inputSpec=u;const d=super.apply(c,e);return this.inputSpec=h,d}else return super.apply(t,e)}call(t,e){return z(()=>{const s=e==null?null:e.mask,r=e==null?null:e.training;let o=e==null?null:e.initialState;t=ct(t),o==null&&(this.stateful?o=this.states_:o=this.getInitialState(t));const i=Array.isArray(this.cell.stateSize)?this.cell.stateSize.length:1;if(o.length!==i)throw new A(`RNN Layer has ${i} state(s) but was passed ${o.length} initial state(s).`);this.unroll&&console.warn("Ignoring unroll = true for RNN layer, due to imperative backend.");const a={training:r},c=Uf((p,g)=>{const m=this.cell.call([p].concat(g),a);return[m[0],m.slice(1)]},t,o,this.goBackwards,s,null,this.unroll,this.returnSequences),u=c[0],h=c[1],d=c[2];this.stateful&&this.resetStates(d,r);const f=this.returnSequences?h:u;return this.returnState?[f].concat(d):f})}getInitialState(t){return z(()=>{let e=ae(t.shape);return e=st(e,[1,2]),e=lr(e),Array.isArray(this.cell.stateSize)?this.cell.stateSize.map(s=>s>1?Ml(e,[1,s]):e):this.cell.stateSize>1?[Ml(e,[1,this.cell.stateSize])]:[e]})}get trainableWeights(){return this.trainable?this.cell.trainableWeights:[]}get nonTrainableWeights(){return this.trainable?this.cell.nonTrainableWeights:this.cell.weights}setFastWeightInitDuringBuild(t){super.setFastWeightInitDuringBuild(t),this.cell!=null&&this.cell.setFastWeightInitDuringBuild(t)}getConfig(){const t=super.getConfig(),e={returnSequences:this.returnSequences,returnState:this.returnState,goBackwards:this.goBackwards,stateful:this.stateful,unroll:this.unroll};this.numConstants!=null&&(e.numConstants=this.numConstants);const s=this.cell.getConfig();return this.getClassName()===On.className&&(e.cell={className:this.cell.getClassName(),config:s}),Object.assign(Object.assign(Object.assign({},s),t),e)}static fromConfig(t,e,s={}){const r=e.cell,o=cn(r,s);return new t(Object.assign(e,{cell:o}))}}On.className="RNN",H(On);class oi extends pt{}class rc extends oi{constructor(t){super(t),this.DEFAULT_ACTIVATION="tanh",this.DEFAULT_KERNEL_INITIALIZER="glorotNormal",this.DEFAULT_RECURRENT_INITIALIZER="orthogonal",this.DEFAULT_BIAS_INITIALIZER="zeros",this.units=t.units,Qt(this.units,"units"),this.activation=Ln(t.activation==null?this.DEFAULT_ACTIVATION:t.activation),this.useBias=t.useBias==null?!0:t.useBias,this.kernelInitializer=Rt(t.kernelInitializer||this.DEFAULT_KERNEL_INITIALIZER),this.recurrentInitializer=Rt(t.recurrentInitializer||this.DEFAULT_RECURRENT_INITIALIZER),this.biasInitializer=Rt(t.biasInitializer||this.DEFAULT_BIAS_INITIALIZER),this.kernelRegularizer=zt(t.kernelRegularizer),this.recurrentRegularizer=zt(t.recurrentRegularizer),this.biasRegularizer=zt(t.biasRegularizer),this.kernelConstraint=Kt(t.kernelConstraint),this.recurrentConstraint=Kt(t.recurrentConstraint),this.biasConstraint=Kt(t.biasConstraint),this.dropout=Ms([1,Mn([0,t.dropout==null?0:t.dropout])]),this.recurrentDropout=Ms([1,Mn([0,t.recurrentDropout==null?0:t.recurrentDropout])]),this.dropoutFunc=t.dropoutFunc,this.stateSize=this.units,this.dropoutMask=null,this.recurrentDropoutMask=null}build(t){t=yt(t),this.kernel=this.addWeight("kernel",[t[t.length-1],this.units],null,this.kernelInitializer,this.kernelRegularizer,!0,this.kernelConstraint),this.recurrentKernel=this.addWeight("recurrent_kernel",[this.units,this.units],null,this.recurrentInitializer,this.recurrentRegularizer,!0,this.recurrentConstraint),this.useBias?this.bias=this.addWeight("bias",[this.units],null,this.biasInitializer,this.biasRegularizer,!0,this.biasConstraint):this.bias=null,this.built=!0}call(t,e){return z(()=>{if(t=t,t.length!==2)throw new A(`SimpleRNNCell expects 2 input Tensors, got ${t.length}.`);let s=t[1];t=t[0];const r=e.training==null?!1:e.training;0<this.dropout&&this.dropout<1&&this.dropoutMask==null&&(this.dropoutMask=_n({ones:()=>Be(t),rate:this.dropout,training:r,dropoutFunc:this.dropoutFunc})),0<this.recurrentDropout&&this.recurrentDropout<1&&this.recurrentDropoutMask==null&&(this.recurrentDropoutMask=_n({ones:()=>Be(s),rate:this.recurrentDropout,training:r,dropoutFunc:this.dropoutFunc}));let o;const i=this.dropoutMask,a=this.recurrentDropoutMask;i!=null?o=an(D(t,i),this.kernel.read()):o=an(t,this.kernel.read()),this.bias!=null&&(o=Ve(o,this.bias.read())),a!=null&&(s=D(s,a));let l=X(o,an(s,this.recurrentKernel.read()));return this.activation!=null&&(l=this.activation.apply(l)),[l,l]})}getConfig(){const t=super.getConfig(),e={units:this.units,activation:zn(this.activation),useBias:this.useBias,kernelInitializer:Ot(this.kernelInitializer),recurrentInitializer:Ot(this.recurrentInitializer),biasInitializer:Ot(this.biasInitializer),kernelRegularizer:Nt(this.kernelRegularizer),recurrentRegularizer:Nt(this.recurrentRegularizer),biasRegularizer:Nt(this.biasRegularizer),activityRegularizer:Nt(this.activityRegularizer),kernelConstraint:jt(this.kernelConstraint),recurrentConstraint:jt(this.recurrentConstraint),biasConstraint:jt(this.biasConstraint),dropout:this.dropout,recurrentDropout:this.recurrentDropout};return Object.assign(Object.assign({},t),e)}}rc.className="SimpleRNNCell",H(rc);class Hf extends On{constructor(t){t.cell=new rc(t),super(t)}call(t,e){return z(()=>{this.cell.dropoutMask!=null&&(dt(this.cell.dropoutMask),this.cell.dropoutMask=null),this.cell.recurrentDropoutMask!=null&&(dt(this.cell.recurrentDropoutMask),this.cell.recurrentDropoutMask=null);const s=e==null?null:e.mask,r=e==null?null:e.training,o=e==null?null:e.initialState;return super.call(t,{mask:s,training:r,initialState:o})})}static fromConfig(t,e){return new t(e)}}Hf.className="SimpleRNN",H(Hf);class oc extends oi{constructor(t){if(super(t),this.DEFAULT_ACTIVATION="tanh",this.DEFAULT_RECURRENT_ACTIVATION="hardSigmoid",this.DEFAULT_KERNEL_INITIALIZER="glorotNormal",this.DEFAULT_RECURRENT_INITIALIZER="orthogonal",this.DEFAULT_BIAS_INITIALIZER="zeros",t.resetAfter)throw new A("GRUCell does not support reset_after parameter set to true.");this.units=t.units,Qt(this.units,"units"),this.activation=Ln(t.activation===void 0?this.DEFAULT_ACTIVATION:t.activation),this.recurrentActivation=Ln(t.recurrentActivation===void 0?this.DEFAULT_RECURRENT_ACTIVATION:t.recurrentActivation),this.useBias=t.useBias==null?!0:t.useBias,this.kernelInitializer=Rt(t.kernelInitializer||this.DEFAULT_KERNEL_INITIALIZER),this.recurrentInitializer=Rt(t.recurrentInitializer||this.DEFAULT_RECURRENT_INITIALIZER),this.biasInitializer=Rt(t.biasInitializer||this.DEFAULT_BIAS_INITIALIZER),this.kernelRegularizer=zt(t.kernelRegularizer),this.recurrentRegularizer=zt(t.recurrentRegularizer),this.biasRegularizer=zt(t.biasRegularizer),this.kernelConstraint=Kt(t.kernelConstraint),this.recurrentConstraint=Kt(t.recurrentConstraint),this.biasConstraint=Kt(t.biasConstraint),this.dropout=Ms([1,Mn([0,t.dropout==null?0:t.dropout])]),this.recurrentDropout=Ms([1,Mn([0,t.recurrentDropout==null?0:t.recurrentDropout])]),this.dropoutFunc=t.dropoutFunc,this.implementation=t.implementation,this.stateSize=this.units,this.dropoutMask=null,this.recurrentDropoutMask=null}build(t){t=yt(t);const e=t[t.length-1];this.kernel=this.addWeight("kernel",[e,this.units*3],null,this.kernelInitializer,this.kernelRegularizer,!0,this.kernelConstraint),this.recurrentKernel=this.addWeight("recurrent_kernel",[this.units,this.units*3],null,this.recurrentInitializer,this.recurrentRegularizer,!0,this.recurrentConstraint),this.useBias?this.bias=this.addWeight("bias",[this.units*3],null,this.biasInitializer,this.biasRegularizer,!0,this.biasConstraint):this.bias=null,this.built=!0}call(t,e){return z(()=>{if(t=t,t.length!==2)throw new A(`GRUCell expects 2 input Tensors (inputs, h, c), got ${t.length}.`);const s=e.training==null?!1:e.training;let r=t[1];t=t[0],0<this.dropout&&this.dropout<1&&this.dropoutMask==null&&(this.dropoutMask=_n({ones:()=>Be(t),rate:this.dropout,training:s,count:3,dropoutFunc:this.dropoutFunc})),0<this.recurrentDropout&&this.recurrentDropout<1&&this.recurrentDropoutMask==null&&(this.recurrentDropoutMask=_n({ones:()=>Be(r),rate:this.recurrentDropout,training:s,count:3,dropoutFunc:this.dropoutFunc}));const o=this.dropoutMask,i=this.recurrentDropoutMask;let a,l,c;0<this.dropout&&this.dropout<1&&(t=D(t,o[0]));let u=an(t,this.kernel.read());this.useBias&&(u=Ve(u,this.bias.read())),0<this.recurrentDropout&&this.recurrentDropout<1&&(r=D(r,i[0]));const h=this.recurrentKernel.read(),[d,f]=en(h,[2*this.units,this.units],h.rank-1),p=an(r,d),[g,m,b]=en(u,3,u.rank-1),[y,k]=en(p,2,p.rank-1);a=this.recurrentActivation.apply(X(g,y)),l=this.recurrentActivation.apply(X(m,k));const w=an(D(l,r),f);c=this.activation.apply(X(b,w));const I=X(D(a,r),D(X(1,se(a)),c));return[I,I]})}getConfig(){const t=super.getConfig(),e={units:this.units,activation:zn(this.activation),recurrentActivation:zn(this.recurrentActivation),useBias:this.useBias,kernelInitializer:Ot(this.kernelInitializer),recurrentInitializer:Ot(this.recurrentInitializer),biasInitializer:Ot(this.biasInitializer),kernelRegularizer:Nt(this.kernelRegularizer),recurrentRegularizer:Nt(this.recurrentRegularizer),biasRegularizer:Nt(this.biasRegularizer),activityRegularizer:Nt(this.activityRegularizer),kernelConstraint:jt(this.kernelConstraint),recurrentConstraint:jt(this.recurrentConstraint),biasConstraint:jt(this.biasConstraint),dropout:this.dropout,recurrentDropout:this.recurrentDropout,implementation:this.implementation,resetAfter:!1};return Object.assign(Object.assign({},t),e)}}oc.className="GRUCell",H(oc);class qf extends On{constructor(t){t.implementation===0&&console.warn("`implementation=0` has been deprecated, and now defaults to `implementation=1`. Please update your layer call."),t.cell=new oc(t),super(t)}call(t,e){return z(()=>{this.cell.dropoutMask!=null&&(dt(this.cell.dropoutMask),this.cell.dropoutMask=null),this.cell.recurrentDropoutMask!=null&&(dt(this.cell.recurrentDropoutMask),this.cell.recurrentDropoutMask=null);const s=e==null?null:e.mask,r=e==null?null:e.training,o=e==null?null:e.initialState;return super.call(t,{mask:s,training:r,initialState:o})})}static fromConfig(t,e){return e.implmentation===0&&(e.implementation=1),new t(e)}}qf.className="GRU",H(qf);class ii extends oi{constructor(t){super(t),this.DEFAULT_ACTIVATION="tanh",this.DEFAULT_RECURRENT_ACTIVATION="hardSigmoid",this.DEFAULT_KERNEL_INITIALIZER="glorotNormal",this.DEFAULT_RECURRENT_INITIALIZER="orthogonal",this.DEFAULT_BIAS_INITIALIZER="zeros",this.units=t.units,Qt(this.units,"units"),this.activation=Ln(t.activation===void 0?this.DEFAULT_ACTIVATION:t.activation),this.recurrentActivation=Ln(t.recurrentActivation===void 0?this.DEFAULT_RECURRENT_ACTIVATION:t.recurrentActivation),this.useBias=t.useBias==null?!0:t.useBias,this.kernelInitializer=Rt(t.kernelInitializer||this.DEFAULT_KERNEL_INITIALIZER),this.recurrentInitializer=Rt(t.recurrentInitializer||this.DEFAULT_RECURRENT_INITIALIZER),this.biasInitializer=Rt(t.biasInitializer||this.DEFAULT_BIAS_INITIALIZER),this.unitForgetBias=t.unitForgetBias,this.kernelRegularizer=zt(t.kernelRegularizer),this.recurrentRegularizer=zt(t.recurrentRegularizer),this.biasRegularizer=zt(t.biasRegularizer),this.kernelConstraint=Kt(t.kernelConstraint),this.recurrentConstraint=Kt(t.recurrentConstraint),this.biasConstraint=Kt(t.biasConstraint),this.dropout=Ms([1,Mn([0,t.dropout==null?0:t.dropout])]),this.recurrentDropout=Ms([1,Mn([0,t.recurrentDropout==null?0:t.recurrentDropout])]),this.dropoutFunc=t.dropoutFunc,this.implementation=t.implementation,this.stateSize=[this.units,this.units],this.dropoutMask=null,this.recurrentDropoutMask=null}build(t){var e;t=yt(t);const s=t[t.length-1];this.kernel=this.addWeight("kernel",[s,this.units*4],null,this.kernelInitializer,this.kernelRegularizer,!0,this.kernelConstraint),this.recurrentKernel=this.addWeight("recurrent_kernel",[this.units,this.units*4],null,this.recurrentInitializer,this.recurrentRegularizer,!0,this.recurrentConstraint);let r;if(this.useBias){if(this.unitForgetBias){const o=this.biasInitializer,i=this.units;r=new(e=class extends Me{apply(l,c){const u=o.apply([i]),h=new zl().apply([i]),d=o.apply([i*2]);return ud(ud(u,h),d)}},e.className="CustomInit",e)}else r=this.biasInitializer;this.bias=this.addWeight("bias",[this.units*4],null,r,this.biasRegularizer,!0,this.biasConstraint)}else this.bias=null;this.built=!0}call(t,e){return z(()=>{const s=e.training==null?!1:e.training;if(t=t,t.length!==3)throw new A(`LSTMCell expects 3 input Tensors (inputs, h, c), got ${t.length}.`);let r=t[1];const o=t[2];t=t[0],0<this.dropout&&this.dropout<1&&this.dropoutMask==null&&(this.dropoutMask=_n({ones:()=>Be(t),rate:this.dropout,training:s,count:4,dropoutFunc:this.dropoutFunc})),0<this.recurrentDropout&&this.recurrentDropout<1&&this.recurrentDropoutMask==null&&(this.recurrentDropoutMask=_n({ones:()=>Be(r),rate:this.recurrentDropout,training:s,count:4,dropoutFunc:this.dropoutFunc}));const i=this.dropoutMask,a=this.recurrentDropoutMask;let l,c,u,h;0<this.dropout&&this.dropout<1&&(t=D(t,i[0]));let d=an(t,this.kernel.read());0<this.recurrentDropout&&this.recurrentDropout<1&&(r=D(r,a[0])),d=X(d,an(r,this.recurrentKernel.read())),this.useBias&&(d=Ve(d,this.bias.read()));const[f,p,g,m]=en(d,4,d.rank-1);l=this.recurrentActivation.apply(f),c=this.recurrentActivation.apply(p),u=X(D(c,o),D(l,this.activation.apply(g))),h=this.recurrentActivation.apply(m);const b=D(h,this.activation.apply(u));return[b,b,u]})}getConfig(){const t=super.getConfig(),e={units:this.units,activation:zn(this.activation),recurrentActivation:zn(this.recurrentActivation),useBias:this.useBias,kernelInitializer:Ot(this.kernelInitializer),recurrentInitializer:Ot(this.recurrentInitializer),biasInitializer:Ot(this.biasInitializer),unitForgetBias:this.unitForgetBias,kernelRegularizer:Nt(this.kernelRegularizer),recurrentRegularizer:Nt(this.recurrentRegularizer),biasRegularizer:Nt(this.biasRegularizer),activityRegularizer:Nt(this.activityRegularizer),kernelConstraint:jt(this.kernelConstraint),recurrentConstraint:jt(this.recurrentConstraint),biasConstraint:jt(this.biasConstraint),dropout:this.dropout,recurrentDropout:this.recurrentDropout,implementation:this.implementation};return Object.assign(Object.assign({},t),e)}}ii.className="LSTMCell",H(ii);class jf extends On{constructor(t){t.implementation===0&&console.warn("`implementation=0` has been deprecated, and now defaults to `implementation=1`. Please update your layer call."),t.cell=new ii(t),super(t)}call(t,e){return z(()=>{this.cell.dropoutMask!=null&&(dt(this.cell.dropoutMask),this.cell.dropoutMask=null),this.cell.recurrentDropoutMask!=null&&(dt(this.cell.recurrentDropoutMask),this.cell.recurrentDropoutMask=null);const s=e==null?null:e.mask,r=e==null?null:e.training,o=e==null?null:e.initialState;return super.call(t,{mask:s,training:r,initialState:o})})}static fromConfig(t,e){return e.implmentation===0&&(e.implementation=1),new t(e)}}jf.className="LSTM",H(jf);class ic extends oi{constructor(t){super(t),this.cells=t.cells}get stateSize(){const t=[];for(const e of this.cells.slice().reverse())Array.isArray(e.stateSize)?t.push(...e.stateSize):t.push(e.stateSize);return t}call(t,e){return z(()=>{t=t;let s=t.slice(1);const r=[];for(const a of this.cells.slice().reverse())Array.isArray(a.stateSize)?r.push(s.splice(0,a.stateSize.length)):r.push(s.splice(0,1));r.reverse();const o=[];let i;for(let a=0;a<this.cells.length;++a){const l=this.cells[a];s=r[a],a===0?i=[t[0]].concat(s):i=[i[0]].concat(s),i=l.call(i,e),o.push(i.slice(1))}s=[];for(const a of o.slice().reverse())s.push(...a);return[i[0]].concat(s)})}build(t){Vl(t)&&(t=t[0]),t=t;let e;this.cells.forEach((s,r)=>{os(`RNNCell_${r}`,()=>{s.build(t),Array.isArray(s.stateSize)?e=s.stateSize[0]:e=s.stateSize,t=[t[0],e]})}),this.built=!0}getConfig(){const t=super.getConfig(),e=o=>({className:o.getClassName(),config:o.getConfig()}),r={cells:this.cells.map(e)};return Object.assign(Object.assign({},t),r)}static fromConfig(t,e,s={}){const r=[];for(const o of e.cells)r.push(cn(o,s));return new t({cells:r})}get trainableWeights(){if(!this.trainable)return[];const t=[];for(const e of this.cells)t.push(...e.trainableWeights);return t}get nonTrainableWeights(){const t=[];for(const e of this.cells)t.push(...e.nonTrainableWeights);if(!this.trainable){const e=[];for(const s of this.cells)e.push(...s.trainableWeights);return e.concat(t)}return t}getWeights(){const t=[];for(const e of this.cells)t.push(...e.weights);return Gl(t)}setWeights(t){const e=[];for(const s of this.cells){const r=s.weights.length,o=t.splice(r);for(let i=0;i<s.weights.length;++i)e.push([s.weights[i],o[i]])}Ul(e)}}ic.className="StackedRNNCells",H(ic);function _n(n){const{ones:t,rate:e,training:s=!1,count:r=1,dropoutFunc:o}=n,i=()=>o!=null?o(t(),e):dd(t(),e),a=()=>ur(i,t,s);return!r||r<=1?Ke(a().clone()):Array(r).fill(void 0).map(a).map(c=>Ke(c.clone()))}/**
 * @license
 * Copyright 2020 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */var Vv=function(n,t){var e={};for(var s in n)Object.prototype.hasOwnProperty.call(n,s)&&t.indexOf(s)<0&&(e[s]=n[s]);if(n!=null&&typeof Object.getOwnPropertySymbols=="function")for(var r=0,s=Object.getOwnPropertySymbols(n);r<s.length;r++)t.indexOf(s[r])<0&&Object.prototype.propertyIsEnumerable.call(n,s[r])&&(e[s[r]]=n[s[r]]);return e};class Kf extends On{constructor(t){if(t.unroll)throw new ut("Unrolling is not possible with convolutional RNNs.");if(Array.isArray(t.cell))throw new ut("It is not possible at the moment to stack convolutional cells.");super(t),this.inputSpec=[new qt({ndim:5})]}call(t,e){return z(()=>{if(this.cell.dropoutMask!=null&&(dt(this.cell.dropoutMask),this.cell.dropoutMask=null),this.cell.recurrentDropoutMask!=null&&(dt(this.cell.recurrentDropoutMask),this.cell.recurrentDropoutMask=null),e&&e.constants)throw new A("ConvRNN2D cell does not support constants");const s=e==null?null:e.mask,r=e==null?null:e.training,o=e==null?null:e.initialState;return super.call(t,{mask:s,training:r,initialState:o})})}computeOutputShape(t){let e=this.computeSingleOutputShape(t);return this.returnSequences||(e=[e[0],...e.slice(2)]),this.returnState&&(e=[e,...Array(2).fill([t[0],...e.slice(-3)])]),e}getInitialState(t){return z(()=>{const{stateSize:e}=this.cell,s=t.shape,r=this.computeSingleOutputShape(s),o=[r[0],...r.slice(2)],i=ae(o);return Array.isArray(e)?Array(e.length).fill(i):[i]})}resetStates(t,e=!1){z(()=>{if(!this.stateful)throw new sn("Cannot call resetStates() on an RNN Layer that is not stateful.");const s=this.inputSpec[0].shape,r=this.computeSingleOutputShape(s),o=[r[0],...r.slice(2)];if(s[0]==null)throw new A("If an RNN is stateful, it needs to know its batch size. Specify the batch size of your input tensors: \n- If using a Sequential model, specify the batch size by passing a `batchInputShape` option to your first layer.\n- If using the functional API, specify the batch size by passing a `batchShape` option to your Input layer.");if(this.getStates()==null)Array.isArray(this.cell.stateSize)?this.states_=this.cell.stateSize.map(()=>ae(o)):this.states_=[ae(o)];else if(t==null)dt(this.states_),this.keptStates!=null&&(dt(this.keptStates),this.keptStates=[]),Array.isArray(this.cell.stateSize)?this.states_=this.cell.stateSize.map(()=>ae(o)):this.states_[0]=ae(o);else{if(Array.isArray(t)||(t=[t]),t.length!==this.states_.length)throw new A(`Layer ${this.name} expects ${this.states_.length} state(s), but it received ${t.length} state value(s). Input received: ${t}`);e?this.keptStates.push(this.states_.slice()):dt(this.states_);for(let a=0;a<this.states_.length;++a){const l=t[a],c=o;if(!oe(l.shape,c))throw new A(`State ${a} is incompatible with layer ${this.name}: expected shape=${c}, received shape=${l.shape}`);this.states_[a]=l}}this.states_=this.states_.map(a=>Ke(a.clone()))})}computeSingleOutputShape(t){const{dataFormat:e,filters:s,kernelSize:r,padding:o,strides:i,dilationRate:a}=this.cell,l=e==="channelsFirst",c=t[l?3:2],u=t[l?4:3],h=He(c,r[0],o,i[0],a[0]),d=He(u,r[1],o,i[1],a[1]);return[...t.slice(0,2),...l?[s,h,d]:[h,d,s]]}}Kf.className="ConvRNN2D";class ac extends ii{constructor(t){const{filters:e,kernelSize:s,strides:r,padding:o,dataFormat:i,dilationRate:a}=t;super(Object.assign(Object.assign({},t),{units:e})),this.filters=e,Qt(this.filters,"filters"),this.kernelSize=zs(s,2,"kernelSize"),this.kernelSize.forEach(l=>Qt(l,"kernelSize")),this.strides=zs(r||1,2,"strides"),this.strides.forEach(l=>Qt(l,"strides")),this.padding=o||"valid",Se(this.padding),this.dataFormat=i||"channelsLast",Wt(this.dataFormat),this.dilationRate=zs(a||1,2,"dilationRate"),this.dilationRate.forEach(l=>Qt(l,"dilationRate"))}build(t){var e;t=yt(t);const s=this.dataFormat==="channelsFirst"?1:t.length-1;if(t[s]==null)throw new A(`The channel dimension of the input should be defined. Found ${t[s]}`);const r=t[s],o=4,i=this.kernelSize.concat([r,this.filters*o]);this.kernel=this.addWeight("kernel",i,null,this.kernelInitializer,this.kernelRegularizer,!0,this.kernelConstraint);const a=this.kernelSize.concat([this.filters,this.filters*o]);if(this.recurrentKernel=this.addWeight("recurrent_kernel",a,null,this.recurrentInitializer,this.recurrentRegularizer,!0,this.recurrentConstraint),this.useBias){let l;if(this.unitForgetBias){const c=this.biasInitializer,u=this.filters;l=new(e=class extends Me{apply(d,f){const p=c.apply([u]),g=Cn([u]),m=c.apply([u*2]);return Fl([p,g,m])}},e.className="CustomInit",e)}else l=this.biasInitializer;this.bias=this.addWeight("bias",[this.filters*o],null,l,this.biasRegularizer,!0,this.biasConstraint)}this.built=!0}call(t,e){return z(()=>{if(t.length!==3)throw new A(`ConvLSTM2DCell expects 3 input Tensors (inputs, h, c), got ${t.length}.`);const s=e.training||!1,r=t[0],o=t[1],i=t[2],a=4;0<this.dropout&&this.dropout<1&&this.dropoutMask==null&&(this.dropoutMask=_n({ones:()=>Be(r),rate:this.dropout,training:s,count:a,dropoutFunc:this.dropoutFunc}));const l=this.dropoutMask,c=(U,q,K)=>!q||!q[K]?U:D(q[K],U);let u=c(r,l,0),h=c(r,l,1),d=c(r,l,2),f=c(r,l,3);0<this.recurrentDropout&&this.recurrentDropout<1&&this.recurrentDropoutMask==null&&(this.recurrentDropoutMask=_n({ones:()=>Be(o),rate:this.recurrentDropout,training:s,count:a,dropoutFunc:this.dropoutFunc}));const p=this.recurrentDropoutMask;let g=c(o,p,0),m=c(o,p,1),b=c(o,p,2),y=c(o,p,3);const k=3,[w,I,S,T]=en(this.kernel.read(),a,k),[C,N,$,x]=this.useBias?en(this.bias.read(),a):[null,null,null,null];u=this.inputConv(u,w,C,this.padding),h=this.inputConv(h,I,N,this.padding),d=this.inputConv(d,S,$,this.padding),f=this.inputConv(f,T,x,this.padding);const[F,M,O,L]=en(this.recurrentKernel.read(),a,k);g=this.recurrentConv(g,F),m=this.recurrentConv(m,M),b=this.recurrentConv(b,O),y=this.recurrentConv(y,L);const B=this.recurrentActivation.apply(X(u,g)),G=this.recurrentActivation.apply(X(h,m)),W=X(D(G,i),D(B,this.activation.apply(X(d,b)))),V=D(this.recurrentActivation.apply(X(f,y)),this.activation.apply(W));return[V,V,W]})}getConfig(){const t=super.getConfig(),{units:e}=t,s=Vv(t,["units"]),r={filters:this.filters,kernelSize:this.kernelSize,padding:this.padding,dataFormat:this.dataFormat,dilationRate:this.dilationRate,strides:this.strides};return Object.assign(Object.assign({},s),r)}inputConv(t,e,s,r){const o=Is(t,e,this.strides,r||"valid",this.dataFormat==="channelsFirst"?"NCHW":"NHWC",this.dilationRate);return s?Ve(o,s,this.dataFormat):o}recurrentConv(t,e){return Is(t,e,1,"same",this.dataFormat==="channelsFirst"?"NCHW":"NHWC")}}ac.className="ConvLSTM2DCell",H(ac);class Xf extends Kf{constructor(t){const e=new ac(t);super(Object.assign(Object.assign({},t),{cell:e}))}static fromConfig(t,e){return new t(e)}}Xf.className="ConvLSTM2D",H(Xf);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class lc extends pt{constructor(t){super(t),this.rate=Math.max(Math.min(t.rate,1),0),this.noiseShape=t.noiseShape,this.seed=t.seed,this.supportsMasking=!0}getNoiseShape(t){if(this.noiseShape==null)return this.noiseShape;const e=t.shape,s=[];for(let r=0;r<this.noiseShape.length;++r)s.push(this.noiseShape[r]==null?e[r]:this.noiseShape[r]);return s}call(t,e){return z(()=>{this.invokeCallHook(t,e);const s=ct(t);if(0<this.rate&&this.rate<1){const r=e.training==null?!1:e.training,o=this.getNoiseShape(s);return ur(()=>dd(s,this.rate,o,this.seed),()=>s,r)}return t})}getConfig(){const t={rate:this.rate,noiseShape:this.noiseShape,seed:this.seed},e=super.getConfig();return Object.assign(t,e),t}dispose(){return super.dispose()}}lc.className="Dropout",H(lc);class Zf extends lc{constructor(t){super(t),this.inputSpec=[{ndim:3}]}getNoiseShape(t){const e=t.shape;return[e[0],1,e[2]]}}Zf.className="SpatialDropout1D",H(Zf);class Jf extends pt{constructor(t){if(super(t),this.activation=null,this.useBias=!0,this.kernel=null,this.bias=null,this.DEFAULT_KERNEL_INITIALIZER="glorotNormal",this.DEFAULT_BIAS_INITIALIZER="zeros",t.batchInputShape==null&&t.inputShape==null&&t.inputDim!=null){let e=null;t.batchSize!=null&&(e=t.batchSize),this.batchInputShape=[e,t.inputDim]}this.units=t.units,Qt(this.units,"units"),this.activation=Ln(t.activation),t.useBias!=null&&(this.useBias=t.useBias),this.kernelInitializer=Rt(t.kernelInitializer||this.DEFAULT_KERNEL_INITIALIZER),this.biasInitializer=Rt(t.biasInitializer||this.DEFAULT_BIAS_INITIALIZER),this.kernelConstraint=Kt(t.kernelConstraint),this.biasConstraint=Kt(t.biasConstraint),this.kernelRegularizer=zt(t.kernelRegularizer),this.biasRegularizer=zt(t.biasRegularizer),this.activityRegularizer=zt(t.activityRegularizer),this.supportsMasking=!0,this.inputSpec=[{minNDim:2}]}build(t){t=yt(t);const e=t[t.length-1];this.kernel==null&&(this.kernel=this.addWeight("kernel",[e,this.units],null,this.kernelInitializer,this.kernelRegularizer,!0,this.kernelConstraint),this.useBias&&(this.bias=this.addWeight("bias",[this.units],null,this.biasInitializer,this.biasRegularizer,!0,this.biasConstraint))),this.inputSpec=[{minNDim:2,axes:{[-1]:e}}],this.built=!0}computeOutputShape(t){t=yt(t);const e=t.slice();return e[e.length-1]=this.units,e}call(t,e){return z(()=>{this.invokeCallHook(t,e);const s=ct(t),r=sd(this.activation.getClassName());let o;return r!=null?o=an(s,this.kernel.read(),r,this.bias?this.bias.read():null):(o=an(s,this.kernel.read()),this.bias!=null&&(o=Ve(o,this.bias.read())),this.activation!=null&&(o=this.activation.apply(o))),o})}getConfig(){const t={units:this.units,activation:zn(this.activation),useBias:this.useBias,kernelInitializer:Ot(this.kernelInitializer),biasInitializer:Ot(this.biasInitializer),kernelRegularizer:Nt(this.kernelRegularizer),biasRegularizer:Nt(this.biasRegularizer),activityRegularizer:Nt(this.activityRegularizer),kernelConstraint:jt(this.kernelConstraint),biasConstraint:jt(this.biasConstraint)},e=super.getConfig();return Object.assign(t,e),t}}Jf.className="Dense",H(Jf);class Yf extends pt{constructor(t){t=t||{},super(t),this.inputSpec=[{minNDim:3}],this.dataFormat=t.dataFormat}computeOutputShape(t){t=yt(t);for(const e of t.slice(1))if(e==null)throw new A(`The shape of the input to "Flatten" is not fully defined (got ${t.slice(1)}). Make sure to pass a complete "input_shape" or "batch_input_shape" argument to the first layer in your model.`);return[t[0],Fn(t,1)]}call(t,e){return z(()=>{this.invokeCallHook(t,e);let s=ct(t);if(this.dataFormat==="channelsFirst"&&s.rank>1){const r=[0];for(let o=2;o<s.rank;++o)r.push(o);r.push(1),s=bt(s,r)}return gx(s)})}getConfig(){const t={};this.dataFormat!=null&&(t.dataFormat=this.dataFormat);const e=super.getConfig();return Object.assign(t,e),t}}Yf.className="Flatten",H(Yf);class Qf extends pt{constructor(t){super(t),this.supportsMasking=!0,this.activation=Ln(t.activation)}call(t,e){return z(()=>{this.invokeCallHook(t,e);const s=ct(t);return this.activation.apply(s)})}getConfig(){const t={activation:zn(this.activation)},e=super.getConfig();return Object.assign(t,e),t}}Qf.className="Activation",H(Qf);class tp extends pt{constructor(t){super(t),this.n=t.n,this.inputSpec=[{ndim:2}]}computeOutputShape(t){return[t[0],this.n,t[1]]}call(t,e){return z(()=>(t=ct(t),px(t,this.n)))}getConfig(){const t={n:this.n},e=super.getConfig();return Object.assign(t,e),t}}tp.className="RepeatVector",H(tp);class ep extends pt{constructor(t){super(t),this.targetShape=t.targetShape;for(let e=0;e<this.targetShape.length;++e)this.isUnknown(this.targetShape[e])&&(this.targetShape[e]=null)}isUnknown(t){return t<0||t==null}fixUnknownDimension(t,e){const s="Total size of new array must be unchanged.",r=e.slice();let o=1,i=null;for(let l=0;l<r.length;++l){const c=r[l];if(this.isUnknown(c))if(i===null)i=l;else throw new A("Can only specifiy one unknown dimension.");else o*=c}const a=Fn(t);if(i!==null){if(o===0||a%o!==0)throw new A(s);r[i]=a/o}else if(a!==o)throw new A(s);return r}computeOutputShape(t){let e=!1;for(let s=0;s<t.length;++s)if(this.isUnknown(t[s])){e=!0;break}return e?t.slice(0,1).concat(this.targetShape):t.slice(0,1).concat(this.fixUnknownDimension(t.slice(1),this.targetShape))}call(t,e){return z(()=>{this.invokeCallHook(t,e);const s=ct(t),r=s.shape,o=r.slice(0,1).concat(this.fixUnknownDimension(r.slice(1),this.targetShape));return _(s,o)})}getConfig(){const t={targetShape:this.targetShape},e=super.getConfig();return Object.assign(t,e),t}}ep.className="Reshape",H(ep);class np extends pt{constructor(t){if(super(t),t.dims==null)throw new Error("Required configuration field `dims` is missing during Permute constructor call.");if(!Array.isArray(t.dims))throw new Error(`Permute constructor requires \`dims\` to be an Array, but received ${t.dims} instead.`);const e=Pe(1,t.dims.length+1);if(!oe(t.dims.slice().sort(),e))throw new Error("Invalid permutation `dims`: "+JSON.stringify(t.dims)+" `dims` must contain consecutive integers starting from 1.");this.dims=t.dims,this.dimsIncludingBatch=[0].concat(this.dims),this.inputSpec=[new qt({ndim:this.dims.length+1})]}computeOutputShape(t){t=yt(t);const e=t.slice();return this.dims.forEach((s,r)=>{e[r+1]=t[s]}),e}call(t,e){return bt(ct(t),this.dimsIncludingBatch)}getConfig(){const t={dims:this.dims},e=super.getConfig();return Object.assign(t,e),t}}np.className="Permute",H(np);class sp extends pt{constructor(t){super(t??{}),this.supportsMasking=!0,t!=null?this.maskValue=t.maskValue==null?0:t.maskValue:this.maskValue=0}computeOutputShape(t){return t}getConfig(){const t=super.getConfig(),e={maskValue:this.maskValue};return Object.assign(e,t),e}computeMask(t,e){const s=ct(t);return Zu(fl(s,this.maskValue),-1)}call(t,e){return z(()=>{this.invokeCallHook(t,e);const s=ct(t),i=Zu(fl(s,this.maskValue),-1,!0);return D(s,Q(i,s.dtype))})}}sp.className="Masking",H(sp);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class rp extends pt{constructor(t){if(super(t),this.embeddings=null,this.DEFAULT_EMBEDDINGS_INITIALIZER="randomUniform",t.batchInputShape==null&&t.inputShape==null){let e=null;t.batchSize!=null&&(e=t.batchSize),t.inputLength==null?this.batchInputShape=[e,null]:this.batchInputShape=[e].concat(xt(t.inputLength))}this.inputDim=t.inputDim,Qt(this.inputDim,"inputDim"),this.outputDim=t.outputDim,Qt(this.outputDim,"outputDim"),this.embeddingsInitializer=Rt(t.embeddingsInitializer||this.DEFAULT_EMBEDDINGS_INITIALIZER),this.embeddingsRegularizer=zt(t.embeddingsRegularizer),this.activityRegularizer=zt(t.activityRegularizer),this.embeddingsConstraint=Kt(t.embeddingsConstraint),this.maskZero=t.maskZero,this.supportsMasking=t.maskZero,this.inputLength=t.inputLength}build(t){this.embeddings=this.addWeight("embeddings",[this.inputDim,this.outputDim],this.dtype,this.embeddingsInitializer,this.embeddingsRegularizer,!0,this.embeddingsConstraint),this.built=!0}warnOnIncompatibleInputShape(t){}computeMask(t,e){return z(()=>this.maskZero?(t=ct(t),fl(t,wt(t))):null)}computeOutputShape(t){if(t=yt(t),this.inputLength==null)return[...t,this.outputDim];const e=xt(this.inputLength);if(e.length!==t.length-1)throw new A(`"inputLength" is ${this.inputLength}, but received input shape has shape ${t}`);{let s=0;for(let r=0;r<e.length;++r){const o=e[r],i=t[r+1];if(o!=null&&i!=null&&o!==i)throw new A(`"inputLength" is ${this.inputLength}, but received input shape has shape ${t}`);o==null&&(e[s]=i),s++}}return[t[0],...e,this.outputDim]}call(t,e){return z(()=>{this.invokeCallHook(t,e);let s=ct(t);s.dtype!=="int32"&&(s=on(s,"int32"));const r=hd(this.embeddings.read(),_(s,[s.size]));return _(r,yt(this.computeOutputShape(s.shape)))})}getConfig(){const t={inputDim:this.inputDim,outputDim:this.outputDim,embeddingsInitializer:Ot(this.embeddingsInitializer),embeddingsRegularizer:Nt(this.embeddingsRegularizer),activityRegularizer:Nt(this.activityRegularizer),embeddingsConstraint:jt(this.embeddingsConstraint),maskZero:this.maskZero,inputLength:this.inputLength},e=super.getConfig();return Object.assign(t,e),t}}rp.className="Embedding",H(rp);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class ls extends pt{constructor(t){super(t||{}),this.supportsMasking=!0}mergeFunction(t){throw new ut}computeElementwiseOpOutputShape(t,e){if(t==null||e==null)return null;if(t.length<e.length)return this.computeElementwiseOpOutputShape(e,t);if(e.length===0)return t;const s=t.slice(0,t.length-e.length);for(let r=0;r<e.length;++r){const o=t[t.length-e.length+r],i=e[r];if(o==null||i==null||o<0||i<0)s.push(null);else if(o===1)s.push(i);else if(i===1)s.push(o);else{if(o!==i)throw new A("Operands could not be broadcast together with shapes "+JSON.stringify(t)+" "+JSON.stringify(e));s.push(o)}}return s}build(t){if(Array.isArray(t)&&!Array.isArray(t[0])&&(t=[yt(t)]),t=t,t.length<2)throw new A(`A merge layer should be called on an Array of at least 2 inputs. Got ${t.length} input(s).`);let e=[];for(const o of t)o!=null&&o[0]!==null&&e.push(o[0]);if(e=Dn(e),e.length>1)throw new A(`Can not merge tensors with different batch sizes. Got tensors with shapes: ${JSON.stringify(t)}.`);let s=t[0]==null?null:t[0].slice(1);for(let o=1;o<t.length;++o){const i=t[o]==null?null:t[o].slice(1);s=this.computeElementwiseOpOutputShape(s,i)}const r=t.map(o=>o.length);t.indexOf(null)===-1&&Dn(r).length===1?this.reshapeRequired=!1:this.reshapeRequired=!0}call(t,e){return z(()=>{if(t=t,this.reshapeRequired){const s=[],r=t.map(o=>o.rank);if(r.indexOf(null)===-1){const o=Mn(r);for(let i of t){const a=i.rank;for(let l=0;l<o-a;++l)i=lr(i,1);s.push(i)}return this.mergeFunction(s)}else{let o=!1;for(const l of t){const c=l.rank;if(c==null){const u=l.shape,h=u[0],d=u.slice(1).concat([h]);let f=_(l,[h].concat(Fn(u.slice(1))));f=bt(f,[1,0]),f=_(f,d),s.push(f),o=!0}else if(c>1){const u=Pe(1,c).concat([0]);s.push(bt(l,u)),o=!0}else s.push(l)}let i=this.mergeFunction(s);const a=i.rank;if(o){if(a==null){const l=i.shape,c=l.length,u=l[c-1],h=[u].concat(l.slice(0,l.length-1));i=_(bt(_(i,[-1,u]),[1,0]),h)}else if(a>1){const l=[a-1].concat(Pe(0,a-1));i=bt(i,l)}}return i}}else return this.mergeFunction(t)})}computeOutputShape(t){t=t;let e;t[0]==null?e=null:e=t[0].slice(1);for(let r=1;r<t.length;++r){const o=t[r]==null?null:t[r].slice(1);e=this.computeElementwiseOpOutputShape(e,o)}let s=[];for(const r of t)r!=null&&r[0]!==null&&s.push(r[0]);return s=Dn(s),s.length===1?e=s.concat(e):e=[null].concat(e),e}computeMask(t,e){return z(()=>{if(e==null)return null;if(!Array.isArray(e))throw new A("`mask` should be an Array");if(!Array.isArray(t))throw new A("`inputs` should be an Array");if(e.length!==t.length)throw new A(`The Array 'inputs' and 'mask' are expected to have the same length, but have different lengths (${t.length} vs ${e.length})`);if(e.every(r=>r==null))return null;e=e.map(r=>r==null?r:we(r,0));let s=e[0];for(let r=1;r<e.length-1;++r)s=Ns(s,e[r]);return s})}}class op extends ls{constructor(t){super(t)}mergeFunction(t){return z(()=>{let e=t[0].clone();for(let s=1;s<t.length;++s)e=X(e,t[s]);return e})}}op.className="Add",H(op);class ip extends ls{constructor(t){super(t)}mergeFunction(t){return z(()=>{let e=t[0].clone();for(let s=1;s<t.length;++s)e=D(e,t[s]);return e})}}ip.className="Multiply",H(ip);class ap extends ls{constructor(t){super(t)}mergeFunction(t){return z(()=>{let e=t[0].clone();for(let s=1;s<t.length;++s)e=X(e,t[s]);return D(1/t.length,e)})}}ap.className="Average",H(ap);class lp extends ls{constructor(t){super(t)}mergeFunction(t){return z(()=>{let e=t[0];for(let s=1;s<t.length;++s)e=es(e,t[s]);return e})}}lp.className="Maximum",H(lp);class cp extends ls{constructor(t){super(t)}mergeFunction(t){return z(()=>{let e=t[0];for(let s=1;s<t.length;++s)e=No(e,t[s]);return e})}}cp.className="Minimum",H(cp);class up extends ls{constructor(t){super(t),this.DEFAULT_AXIS=-1,t==null&&(t={}),this.axis=t.axis==null?this.DEFAULT_AXIS:t.axis,this.supportsMasking=!0,this.reshapeRequired=!1}build(t){if(!(Array.isArray(t)&&Array.isArray(t[0]))||t.length===1)throw new A("A `Concatenate` layer should be called on a list of at least 2 inputs");t=t;let e=!0;for(const r of t)if(r!=null){e=!1;break}if(e)return;const s=[];for(let r=0;r<t.length;++r){const o=t[r].slice();o.splice(this.axis,1);let i=!1;for(const a of s)if(oe(a,o)){i=!0;break}i||s.push(o)}if(s.length>1)throw new A("A `Concatenate` layer requires inputs with matching shapes except for the concat axis. Got input shapes: "+JSON.stringify(t))}mergeFunction(t){return z(()=>Fl(t,this.axis))}computeOutputShape(t){if(!(Array.isArray(t)&&Array.isArray(t[0])))throw new A("A `Concatenate` layer should be called on a list of inputs.");const e=t,s=e[0].slice(),r=this.axis<0?s.length+this.axis:this.axis;for(const o of e.slice(1)){if(s[r]==null||o[r]==null){s[r]=null;break}s[r]+=o[r]}return s}computeMask(t,e){if(e==null)return null;if(!Array.isArray(e))throw new A("`mask` should be an array for Concatenate");if(!Array.isArray(t))throw new A("`inputs` should be an array for Concatenate");if(e.length!==t.length)throw new A(`Mismatch in the length of mask (${e.length}) and the legnth of inputs (${t.length})`);return z(()=>{let s=!0;if(e.forEach(i=>{if(i!=null){s=!1;return}}),s)return null;const r=[];for(let i=0;i<t.length;++i)e[i]==null?r.push(Q(Be(t[i]),"bool")):e[i].rank<t[i].rank?r.push(we(e[i],-1)):r.push(e[i]);const o=_e(r,this.axis);return Lb(o,-1,!1)})}getConfig(){const t={axis:this.axis},e=super.getConfig();return Object.assign(t,e),t}}up.className="Concatenate",H(up);function kr(n,t){for(;n<0;)n+=t;return n}function Gv(n,t,e){if(n.shape.length>3||t.shape.length>3)throw new ut("batchDot is not implemented for tensors of 4D or higher rank yet");if(v(n.shape.length>=2,()=>`batchDot requires the rank of x to be >= 2, but got ${n.shape.length}`),v(n.shape.length>=2,()=>`batchDot requires the rank of y to be >= 2, but got ${t.shape.length}`),typeof e=="number"&&(e=[e,e]),n.dtype==="complex64"||t.dtype==="complex64")throw new ut("batchDot is not implemented for complex64-type Tensors yet.");const s=n.shape.length,r=t.shape.length;e==null&&(e=[s-1,r-2]);const o=e;return z(()=>{let i;if(s>r){i=s-r;const l=[];for(let c=0;c<i;++c)l.push(1);t=_(t,t.shape.concat(l))}else if(r>s){i=r-s;const l=[];for(let c=0;c<i;++c)l.push(1);n=_(n,n.shape.concat(l))}else i=0;let a;if(n.shape.length===2&&t.shape.length===2)o[0]===o[1]?a=st(D(n,t),o[0]):a=st(D(bt(n,[1,0]),t),o[1]);else{const l=o[0]!==n.shape.length-1,c=o[1]===t.shape.length-1;a=Tt(n,t,l,c)}if(i>0){let l;s>r?l=s+r-3:l=s-1;const c=[];for(let u=l;u<l+i;++u)c.push(u);a=zo(a,c)}return a.shape.length===1&&(a=we(a,1)),a})}class hp extends ls{constructor(t){super(t),this.axes=t.axes,this.normalize=t.normalize==null?!1:t.normalize,this.supportsMasking=!0,this.reshapeRequired=!1}build(t){v(Array.isArray(t)&&t.length===2&&Array.isArray(t[0])&&Array.isArray(t[1]),()=>"A `Dot` layer should be called on a list of exactly 2 inputs.");const e=t[0],s=t[1];if(e.length>3||s.length>3)throw new ut("Dot layer does not support tensors of 4D or higher rank yet.");const r=this.interpretAxes(e,s);if(e[r[0]]!==s[r[1]])throw new A(`Dimension incompatibility: ${e[r[0]]} !== ${s[r[1]]}`)}mergeFunction(t){if(t.length!==2)throw new A(`A \`Dot\` layer must be called on exactly 2 inputs, but received ${t.length} input(s).`);let e=t[0],s=t[1],r;return Array.isArray(this.axes)?r=this.axes.map((o,i)=>kr(o,t[i].shape.length)):r=[kr(this.axes,e.shape.length),kr(this.axes,s.shape.length)],this.normalize&&(e=Ko(e,r[0]),s=Ko(s,r[1])),Gv(e,s,r)}interpretAxes(t,e){let s;return Array.isArray(this.axes)?s=this.axes:s=[kr(this.axes,t.length),kr(this.axes,e.length)],s}computeOutputShape(t){v(Array.isArray(t)&&t.length===2&&Array.isArray(t[0])&&Array.isArray(t[1]),()=>"A `Dot` layer should be called on a list of exactly 2 inputs.");const e=t[0].slice(),s=t[1].slice();if(e.length>3||s.length>3)throw new ut("Dot layer does not support tensors of 4D or higher rank yet.");const r=this.interpretAxes(e,s);e.splice(r[0],1),s.splice(r[1],1),s.splice(0,1);const o=e.concat(s);return o.length===1&&o.push(1),o}computeMask(t,e){return null}getConfig(){const t={axes:this.axes,normalize:this.normalize},e=super.getConfig();return Object.assign(t,e),t}}hp.className="Dot",H(hp);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class dp extends pt{constructor(t){super(t),this.supportsMasking=!0,this.stddev=t.stddev}computeOutputShape(t){return t}getConfig(){const t=super.getConfig(),e={stddev:this.stddev};return Object.assign(e,t),e}call(t,e){return z(()=>{this.invokeCallHook(t,e);const s=ct(t);return ur(()=>X(Vo(s.shape,0,this.stddev),s),()=>s,e.training||!1)})}}dp.className="GaussianNoise",H(dp);class fp extends pt{constructor(t){super(t),this.supportsMasking=!0,this.rate=t.rate}computeOutputShape(t){return t}getConfig(){const t=super.getConfig(),e={rate:this.rate};return Object.assign(e,t),e}call(t,e){return z(()=>{this.invokeCallHook(t,e);const s=ct(t);return this.rate>0&&this.rate<1?ur(()=>{const o=Math.sqrt(this.rate/(1-this.rate));return D(s,Vo(s.shape,1,o))},()=>s,e.training||!1):s})}}fp.className="GaussianDropout",H(fp);class pp extends pt{constructor(t){super(t),this.supportsMasking=!0,this.rate=t.rate,this.noiseShape=t.noiseShape}_getNoiseShape(t){return this.noiseShape||ct(t).shape}computeOutputShape(t){return t}getConfig(){const t=super.getConfig(),e={rate:this.rate};return Object.assign(e,t),e}call(t,e){return z(()=>{if(this.rate<1&&this.rate>0){const s=this._getNoiseShape(t);return ur(()=>{const o=ct(t),a=-1.6732632423543772*1.0507009873554805;let l=vs(sr(s),this.rate);l=on(l,"float32");const c=((1-this.rate)*(1+this.rate*a**2))**-.5,u=-c*a*this.rate,h=X(D(o,l),D(X(l,-1),a));return X(D(h,c),u)},()=>ct(t),e.training||!1)}return t})}}pp.className="AlphaDropout",H(pp);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function xr(n,t,e,s,r,o=.001){let i;if(n.rank===2)i=ry(n,t,e,s,r,o);else if(n.rank===3)i=iy(n,t,e,s,r,o);else if(n.rank===4)i=ly(n,t,e,s,r,o);else throw new ut(`batchNormalization is not implemented for array of rank ${n.rank} yet`);return i}function Uv(n,t,e,s,r=.001){return z(()=>{const o=dl(n,s),i=o.mean,a=o.variance;return[xr(n,i,a,e,t,r),i,a]})}function Hv(n,t,e,s,r=.001){return z(()=>{const o=dl(n,s),i=o.mean,a=o.variance,l=[];for(const p of Pe(0,n.rank))s.indexOf(p)!==-1?l.push(1):l.push(n.shape[p]);const c=_(i,l),u=_(a,l),h=t==null?null:_(t,l),d=e==null?null:_(e,l);return[xr(n,c,u,d,h,r),i,a]})}function qv(n,t,e,s,r=.001){return oe(s.slice().sort(),Pe(0,n.rank-1))?Uv(n,t,e,s,r):Hv(n,t,e,s,r)}class mp extends pt{constructor(t){t==null&&(t={}),super(t),this.supportsMasking=!0,this.axis=t.axis==null?-1:t.axis,this.momentum=t.momentum==null?.99:t.momentum,this.epsilon=t.epsilon==null?.001:t.epsilon,this.center=t.center==null?!0:t.center,this.scale=t.scale==null?!0:t.scale,this.betaInitializer=Rt(t.betaInitializer||"zeros"),this.gammaInitializer=Rt(t.gammaInitializer||"ones"),this.movingMeanInitializer=Rt(t.movingMeanInitializer||"zeros"),this.movingVarianceInitializer=Rt(t.movingVarianceInitializer||"ones"),this.betaConstraint=Kt(t.betaConstraint),this.gammaConstraint=Kt(t.gammaConstraint),this.betaRegularizer=zt(t.betaRegularizer),this.gammaRegularizer=zt(t.gammaRegularizer)}build(t){t=yt(t);const e=this.axis>=0?this.axis:this.axis+t.length,s=t[e];if(s==null)throw new A(`Axis ${e} of input tensor should have a defined dimension but the layer received an input with shape ${JSON.stringify(t)}.`);this.inputSpec=[new qt({ndim:t.length,axes:{[e]:s}})];const r=[s];this.scale&&(this.gamma=this.addWeight("gamma",r,null,this.gammaInitializer,this.gammaRegularizer,!0,this.gammaConstraint)),this.center&&(this.beta=this.addWeight("beta",r,null,this.betaInitializer,this.betaRegularizer,!0,this.betaConstraint)),this.movingMean=this.addWeight("moving_mean",r,null,this.movingMeanInitializer,null,!1),this.movingVariance=this.addWeight("moving_variance",r,null,this.movingVarianceInitializer,null,!1),this.built=!0}call(t,e){return z(()=>{const s=e.training==null?!1:e.training,r=ct(t),o=r.shape,i=o.length,a=Pe(0,i),l=this.axis>=0?this.axis:this.axis+i;a.splice(l,1);const c=ns(1,i);c[l]=o[l];const u=a.slice();u.sort();const h=!oe(u,Pe(0,i).slice(0,i-1)),d=()=>{if(h){const y=_(this.movingMean.read(),c),k=_(this.movingVariance.read(),c),w=this.center?_(this.beta.read(),c):null,I=this.scale?_(this.gamma.read(),c):null;return xr(r,y,k,w,I,this.epsilon)}else return xr(r,this.movingMean.read(),this.movingVariance.read(),this.beta==null?null:this.beta.read(),this.gamma==null?null:this.gamma.read(),this.epsilon)};if(!s)return d();const[f,p,g]=qv(r,this.gamma.read(),this.beta.read(),a,this.epsilon),m=(y,k,w)=>{z(()=>{const I=1-w,S=y.read(),T=D(lt(S,k),I);y.write(lt(S,T))})};return(()=>{m(this.movingMean,p,this.momentum),m(this.movingVariance,g,this.momentum)})(),f})}getConfig(){const t={axis:this.axis,momentum:this.momentum,epsilon:this.epsilon,center:this.center,scale:this.scale,betaInitializer:Ot(this.betaInitializer),gammaInitializer:Ot(this.gammaInitializer),movingMeanInitializer:Ot(this.movingMeanInitializer),movingVarianceInitializer:Ot(this.movingVarianceInitializer),betaRegularizer:Nt(this.betaRegularizer),gammaRegularizer:Nt(this.gammaRegularizer),betaConstraint:jt(this.betaConstraint),gammaConstraint:jt(this.gammaConstraint)},e=super.getConfig();return Object.assign(t,e),t}}mp.className="BatchNormalization",H(mp);class gp extends pt{constructor(t){if(t==null&&(t={}),super(t),this.axis=t.axis==null?-1:t.axis,typeof this.axis=="number"){if(!Number.isInteger(this.axis))throw new Error(`Expected axis to be an integer, but received ${this.axis}`)}else if(Array.isArray(this.axis)){for(const e of this.axis)if(!Number.isInteger(e))throw new Error(`Expected axis to be an array of integers, but received ${JSON.stringify(this.axis)}`)}else throw new Error(`Expected axis to be an integer or an array of integers, but received ${JSON.stringify(this.axis)}`);this.epsilon=t.epsilon==null?.001:t.epsilon,this.center=t.center==null?!0:t.center,this.scale=t.scale==null?!0:t.scale,this.betaInitializer=Rt(t.betaInitializer||"zeros"),this.gammaInitializer=Rt(t.gammaInitializer||"ones"),this.betaRegularizer=zt(t.betaRegularizer),this.gammaRegularizer=zt(t.gammaRegularizer),this.supportsMasking=!0}build(t){t=yt(t);const e=t.length;typeof this.axis=="number"&&(this.axis=[this.axis]);for(let o=0;o<this.axis.length;++o)this.axis[o]<0&&(this.axis[o]+=e);for(const o of this.axis)if(o<0||o>=e)throw new Error(`Invalid axis: ${o}`);if(this.axis.length!==Dn(this.axis).length)throw new Error(`Found duplicate axes in: ${this.axis}`);const s=this.axis.map(o=>t[o]),r=!0;this.scale?this.gamma=this.addWeight("gamma",s,"float32",this.gammaInitializer,this.gammaRegularizer,r):this.gamma=null,this.center?this.beta=this.addWeight("beta",s,"float32",this.betaInitializer,this.betaRegularizer,r):this.beta=null,this.built=!0}call(t,e){const s=ct(t),r=s.shape,o=r.length;return z(()=>{let{mean:a,variance:l}=dl(s,this.axis,!0);const c=ns(1,o);for(const g of this.axis)c[g]=r[g];const u=g=>g!=null&&g.shape.length!==o?_(g,c):g;let h=this.scale?u(this.gamma.read()):null,d=this.center?u(this.beta.read()):null;const f=[],p=[];for(let g=0;g<o;++g)this.axis.indexOf(g)!==-1?(f.push(r[g]),p.push(1)):(f.push(1),p.push(r[g]));return a=tn(a,f),l=tn(l,f),h!=null&&(h=tn(h,p)),d!=null&&(d=tn(d,p)),xr(s,a,l,d,h,this.epsilon)})}getConfig(){const t={axis:this.axis,epsilon:this.epsilon,center:this.center,scale:this.scale,betaInitializer:Ot(this.betaInitializer),gammaInitializer:Ot(this.gammaInitializer),betaRegularizer:Nt(this.betaRegularizer),gammaRegularizer:Nt(this.gammaRegularizer)},e=super.getConfig();return Object.assign(t,e),t}}gp.className="LayerNormalization",H(gp);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function jv(n,t,e){return z(()=>{if(n.rank!==4)throw new A(`temporalPadding expects input tensor to be 4-D, but received a ${n.rank}-D tensor.`);if(t==null&&(t=[[1,1],[1,1]]),t.length!==2||t[0].length!==2||t[1].length!==2)throw new A("spatial2dPadding expects `padding` to be an Array of two Arrays, each of which is an Array of two integers.");if(e==null&&(e=We()),e!=="channelsLast"&&e!=="channelsFirst")throw new A(`Unknown data format: ${e}. Supported data formats are 'channelsLast' and 'channelsFirst.`);let s;return e==="channelsFirst"?s=[[0,0],[0,0],t[0],t[1]]:s=[[0,0],t[0],t[1],[0,0]],ch(n,s)})}class bp extends pt{constructor(t){if(t==null&&(t={}),super(t),this.dataFormat=t.dataFormat==null?We():t.dataFormat,t.padding==null)this.padding=[[1,1],[1,1]];else if(typeof t.padding=="number")this.padding=[[t.padding,t.padding],[t.padding,t.padding]];else{if(t.padding=t.padding,t.padding.length!==2)throw new A(`ZeroPadding2D expects padding to be a length-2 array, but received a length-${t.padding.length} array.`);let e,s;if(typeof t.padding[0]=="number")e=[t.padding[0],t.padding[0]],s=[t.padding[1],t.padding[1]];else{if(t.padding=t.padding,t.padding[0].length!==2)throw new A(`ZeroPadding2D expects height padding to be a length-2 array, but received a length-${t.padding[0].length} array.`);if(e=t.padding[0],t.padding[1].length!==2)throw new A(`ZeroPadding2D expects width padding to be a length-2 array, but received a length-${t.padding[1].length} array.`);s=t.padding[1]}this.padding=[e,s]}this.inputSpec=[new qt({ndim:4})]}computeOutputShape(t){t=yt(t);let e,s;return this.dataFormat==="channelsFirst"?(t[2]!=null&&t[2]>=0?e=t[2]+this.padding[0][0]+this.padding[0][1]:e=null,t[3]!=null&&t[3]>=0?s=t[3]+this.padding[1][0]+this.padding[1][1]:s=null,[t[0],t[1],e,s]):(t[1]!=null&&t[1]>=0?e=t[1]+this.padding[0][0]+this.padding[0][1]:e=null,t[2]!=null&&t[2]>=0?s=t[2]+this.padding[1][0]+this.padding[1][1]:s=null,[t[0],e,s,t[3]])}call(t,e){return z(()=>jv(ct(t),this.padding,this.dataFormat))}getConfig(){const t={padding:this.padding,dataFormat:this.dataFormat},e=super.getConfig();return Object.assign(t,e),t}}bp.className="ZeroPadding2D",H(bp);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function ai(n,t,e,s,r,o){return z(()=>{Wt(r),od(o),Se(s),e==null&&(e=[1,1]),s==null&&(s="valid"),r==null&&(r=We()),o==null&&(o="max"),n=sc(n,r);let i;const a=s==="same"?"same":"valid";return o==="max"?i=A0(n,t,e,a):i=Hb(n,t,e,a),r==="channelsFirst"&&(i=bt(i,[0,3,1,2])),i})}function yp(n,t,e,s,r,o){return z(()=>{Wt(r),od(o),Se(s),e==null&&(e=[1,1,1]),s==null&&(s="valid"),r==null&&(r=We()),o==null&&(o="max"),n=Rf(n,r);let i;const a=s==="same"?"same":"valid";return o==="max"?i=D0(n,t,e,a):i=jb(n,t,e,a),r==="channelsFirst"&&(i=bt(i,[0,4,1,2,3])),i})}class wp extends pt{constructor(t){if(t.poolSize==null&&(t.poolSize=2),super(t),typeof t.poolSize=="number")this.poolSize=[t.poolSize];else if(Array.isArray(t.poolSize)&&t.poolSize.length===1&&typeof t.poolSize[0]=="number")this.poolSize=t.poolSize;else throw new A(`poolSize for 1D convolutional layer must be a number or an Array of a single number, but received ${JSON.stringify(t.poolSize)}`);if(Qt(this.poolSize,"poolSize"),t.strides==null)this.strides=this.poolSize;else if(typeof t.strides=="number")this.strides=[t.strides];else if(Array.isArray(t.strides)&&t.strides.length===1&&typeof t.strides[0]=="number")this.strides=t.strides;else throw new A(`strides for 1D convolutional layer must be a number or an Array of a single number, but received ${JSON.stringify(t.strides)}`);Qt(this.strides,"strides"),this.padding=t.padding==null?"valid":t.padding,Se(this.padding),this.inputSpec=[new qt({ndim:3})]}computeOutputShape(t){t=yt(t);const e=He(t[1],this.poolSize[0],this.padding,this.strides[0]);return[t[0],e,t[2]]}call(t,e){return z(()=>{this.invokeCallHook(t,e),t=lr(ct(t),2);const s=this.poolingFunction(ct(t),[this.poolSize[0],1],[this.strides[0],1],this.padding,"channelsLast");return zo(s,[2])})}getConfig(){const t={poolSize:this.poolSize,padding:this.padding,strides:this.strides},e=super.getConfig();return Object.assign(t,e),t}}class kp extends wp{constructor(t){super(t)}poolingFunction(t,e,s,r,o){return Wt(o),Se(r),ai(t,e,s,r,o,"max")}}kp.className="MaxPooling1D",H(kp);class xp extends wp{constructor(t){super(t)}poolingFunction(t,e,s,r,o){return Wt(o),Se(r),ai(t,e,s,r,o,"avg")}}xp.className="AveragePooling1D",H(xp);class Ip extends pt{constructor(t){if(t.poolSize==null&&(t.poolSize=[2,2]),super(t),this.poolSize=Array.isArray(t.poolSize)?t.poolSize:[t.poolSize,t.poolSize],t.strides==null)this.strides=this.poolSize;else if(Array.isArray(t.strides)){if(t.strides.length!==2)throw new A(`If the strides property of a 2D pooling layer is an Array, it is expected to have a length of 2, but received length ${t.strides.length}.`);this.strides=t.strides}else this.strides=[t.strides,t.strides];Qt(this.poolSize,"poolSize"),Qt(this.strides,"strides"),this.padding=t.padding==null?"valid":t.padding,this.dataFormat=t.dataFormat==null?"channelsLast":t.dataFormat,Wt(this.dataFormat),Se(this.padding),this.inputSpec=[new qt({ndim:4})]}computeOutputShape(t){t=yt(t);let e=this.dataFormat==="channelsFirst"?t[2]:t[1],s=this.dataFormat==="channelsFirst"?t[3]:t[2];return e=He(e,this.poolSize[0],this.padding,this.strides[0]),s=He(s,this.poolSize[1],this.padding,this.strides[1]),this.dataFormat==="channelsFirst"?[t[0],t[1],e,s]:[t[0],e,s,t[3]]}call(t,e){return z(()=>(this.invokeCallHook(t,e),this.poolingFunction(ct(t),this.poolSize,this.strides,this.padding,this.dataFormat)))}getConfig(){const t={poolSize:this.poolSize,padding:this.padding,strides:this.strides,dataFormat:this.dataFormat},e=super.getConfig();return Object.assign(t,e),t}}class Sp extends Ip{constructor(t){super(t)}poolingFunction(t,e,s,r,o){return Wt(o),Se(r),ai(t,e,s,r,o,"max")}}Sp.className="MaxPooling2D",H(Sp);class vp extends Ip{constructor(t){super(t)}poolingFunction(t,e,s,r,o){return Wt(o),Se(r),ai(t,e,s,r,o,"avg")}}vp.className="AveragePooling2D",H(vp);class Np extends pt{constructor(t){if(t.poolSize==null&&(t.poolSize=[2,2,2]),super(t),this.poolSize=Array.isArray(t.poolSize)?t.poolSize:[t.poolSize,t.poolSize,t.poolSize],t.strides==null)this.strides=this.poolSize;else if(Array.isArray(t.strides)){if(t.strides.length!==3)throw new A(`If the strides property of a 3D pooling layer is an Array, it is expected to have a length of 3, but received length ${t.strides.length}.`);this.strides=t.strides}else this.strides=[t.strides,t.strides,t.strides];Qt(this.poolSize,"poolSize"),Qt(this.strides,"strides"),this.padding=t.padding==null?"valid":t.padding,this.dataFormat=t.dataFormat==null?"channelsLast":t.dataFormat,Wt(this.dataFormat),Se(this.padding),this.inputSpec=[new qt({ndim:5})]}computeOutputShape(t){t=yt(t);let e=this.dataFormat==="channelsFirst"?t[2]:t[1],s=this.dataFormat==="channelsFirst"?t[3]:t[2],r=this.dataFormat==="channelsFirst"?t[4]:t[3];return e=He(e,this.poolSize[0],this.padding,this.strides[0]),s=He(s,this.poolSize[1],this.padding,this.strides[1]),r=He(r,this.poolSize[2],this.padding,this.strides[2]),this.dataFormat==="channelsFirst"?[t[0],t[1],e,s,r]:[t[0],e,s,r,t[4]]}call(t,e){return z(()=>(this.invokeCallHook(t,e),this.poolingFunction(ct(t),this.poolSize,this.strides,this.padding,this.dataFormat)))}getConfig(){const t={poolSize:this.poolSize,padding:this.padding,strides:this.strides,dataFormat:this.dataFormat},e=super.getConfig();return Object.assign(t,e),t}}class $p extends Np{constructor(t){super(t)}poolingFunction(t,e,s,r,o){return Wt(o),Se(r),yp(t,e,s,r,o,"max")}}$p.className="MaxPooling3D",H($p);class Tp extends Np{constructor(t){super(t)}poolingFunction(t,e,s,r,o){return Wt(o),Se(r),yp(t,e,s,r,o,"avg")}}Tp.className="AveragePooling3D",H(Tp);class Cp extends pt{constructor(t){super(t),this.inputSpec=[new qt({ndim:3})]}computeOutputShape(t){return[t[0],t[2]]}call(t,e){throw new ut}}class Ap extends Cp{constructor(t){super(t||{})}call(t,e){return z(()=>{const s=ct(t);return Ut(s,1)})}}Ap.className="GlobalAveragePooling1D",H(Ap);class Ep extends Cp{constructor(t){super(t||{})}call(t,e){return z(()=>{const s=ct(t);return Qe(s,1)})}}Ep.className="GlobalMaxPooling1D",H(Ep);class Dp extends pt{constructor(t){super(t),this.dataFormat=t.dataFormat==null?"channelsLast":t.dataFormat,Wt(this.dataFormat),this.inputSpec=[new qt({ndim:4})]}computeOutputShape(t){return t=t,this.dataFormat==="channelsLast"?[t[0],t[3]]:[t[0],t[1]]}call(t,e){throw new ut}getConfig(){const t={dataFormat:this.dataFormat},e=super.getConfig();return Object.assign(t,e),t}}class Fp extends Dp{call(t,e){return z(()=>{const s=ct(t);return this.dataFormat==="channelsLast"?Ut(s,[1,2]):Ut(s,[2,3])})}}Fp.className="GlobalAveragePooling2D",H(Fp);class Mp extends Dp{call(t,e){return z(()=>{const s=ct(t);return this.dataFormat==="channelsLast"?Qe(s,[1,2]):Qe(s,[2,3])})}}Mp.className="GlobalMaxPooling2D",H(Mp);/**
 * @license
 * Copyright 2018 Google LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class Rp extends pt{constructor(t){super(t),this.layer=t.layer}build(t){this.built=!0}get trainable(){return this.layer!=null?this.layer.trainable:!1}set trainable(t){this.layer!=null&&(this.layer.trainable=t)}get trainableWeights(){return this.layer.trainableWeights}get nonTrainableWeights(){return this.layer.nonTrainableWeights}get updates(){return this.layer._updates}get losses(){return this.layer.losses}getWeights(){return this.layer.getWeights()}setWeights(t){this.layer.setWeights(t)}getConfig(){const t={layer:{className:this.layer.getClassName(),config:this.layer.getConfig()}},e=super.getConfig();return Object.assign(t,e),t}setFastWeightInitDuringBuild(t){super.setFastWeightInitDuringBuild(t),this.layer!=null&&this.layer.setFastWeightInitDuringBuild(t)}static fromConfig(t,e,s={}){const r=e.layer,o=cn(r,s);delete e.layer;const i={layer:o};return Object.assign(i,e),new t(i)}}class zp extends Rp{constructor(t){super(t),this.supportsMasking=!0}build(t){if(t=yt(t),t.length<3)throw new A(`TimeDistributed layer expects an input shape >= 3D, but received input shape ${JSON.stringify(t)}`);this.inputSpec=[{shape:t}];const e=[t[0]].concat(t.slice(2));this.layer.built||(this.layer.build(e),this.layer.built=!0),super.build(t)}computeOutputShape(t){t=yt(t);const e=[t[0]].concat(t.slice(2)),s=this.layer.computeOutputShape(e),r=t[1];return[s[0],r].concat(s.slice(1))}call(t,e){return z(()=>(t=ct(t),Uf((i,a)=>[ct(this.layer.call(i,e)),[]],t,[],!1,null,null,!1,!0)[1]))}}zp.className="TimeDistributed",H(zp);function Kv(n){rs(cx,"BidirectionalMergeMode",n)}const Xv="concat";class Lp extends Rp{constructor(t){super(t);const e=t.layer.getConfig(),s={};s.className=t.layer.getClassName(),s.config=e,this.forwardLayer=cn(s),e.goBackwards=e.goBackwards!==!0;const r={};if(r.className=t.layer.getClassName(),r.config=e,this.backwardLayer=cn(r),this.forwardLayer.name="forward_"+this.forwardLayer.name,this.backwardLayer.name="backward_"+this.backwardLayer.name,this.mergeMode=t.mergeMode===void 0?Xv:t.mergeMode,Kv(this.mergeMode),t.weights)throw new ut("weights support is not implemented for Bidirectional layer yet.");this._stateful=t.layer.stateful,this.returnSequences=t.layer.returnSequences,this.returnState=t.layer.returnState,this.supportsMasking=!0,this._trainable=!0,this.inputSpec=t.layer.inputSpec,this.numConstants=null}get trainable(){return this._trainable}set trainable(t){this._trainable=t,this.forwardLayer!=null&&(this.forwardLayer.trainable=t),this.backwardLayer!=null&&(this.backwardLayer.trainable=t)}getWeights(){return this.forwardLayer.getWeights().concat(this.backwardLayer.getWeights())}setWeights(t){const e=t.length,s=Math.floor(e/2);this.forwardLayer.setWeights(t.slice(0,s)),this.backwardLayer.setWeights(t.slice(s))}computeOutputShape(t){let e=this.forwardLayer.computeOutputShape(t);Array.isArray(e)&&Array.isArray(e[0])||(e=[e]),e=e;let s,r,o;return this.returnState&&(o=e.slice(1)),s=e[0],s=s,this.mergeMode==="concat"?(s[s.length-1]*=2,r=[s]):this.mergeMode==null?r=[s,s.slice()]:r=[s],this.returnState?this.mergeMode==null?r.concat(o).concat(o.slice()):[s].concat(o).concat(o.slice()):pe(r)}apply(t,e){let s=e==null?null:e.initialState,r=e==null?null:e.constants;e==null&&(e={});const o=Gf(t,s,r,this.numConstants);if(t=o.inputs,s=o.initialState,r=o.constants,Array.isArray(t)&&(s=t.slice(1),t=t[0]),(s==null||s.length===0)&&r==null)return super.apply(t,e);const i=[],a=[];if(s!=null){const c=s.length;if(c%2>0)throw new A("When passing `initialState` to a Bidrectional RNN, the state should be an Array containing the states of the underlying RNNs.");e.initialState=s,i.push(...s);const u=s.map(h=>new qt({shape:h.shape}));this.forwardLayer.stateSpec=u.slice(0,c/2),this.backwardLayer.stateSpec=u.slice(c/2),a.push(...u)}if(r!=null)throw new ut("Support for constants in Bidirectional layers is not implemented yet.");const l=i[0]instanceof ln;for(const c of i)if(c instanceof ln!==l)throw new A("The initial state of a Bidirectional layer cannot be specified as a mix of symbolic and non-symbolic tensors");if(l){const c=[t].concat(i),u=this.inputSpec.concat(a),h=this.inputSpec;this.inputSpec=u;const d=super.apply(c,e);return this.inputSpec=h,d}else return super.apply(t,e)}call(t,e){return z(()=>{const s=e.initialState;let r,o;if(s==null)r=this.forwardLayer.call(t,e),o=this.backwardLayer.call(t,e);else{const l=s.slice(0,s.length/2),c=s.slice(s.length/2);r=this.forwardLayer.call(t,Object.assign(e,{initialState:l})),o=this.backwardLayer.call(t,Object.assign(e,{initialState:c}))}let i;this.returnState&&(Array.isArray(r)&&(i=r.slice(1).concat(o.slice(1))),r=r[0],o=o[0]),this.returnSequences&&(o=Mo(o,1));let a;return this.mergeMode==="concat"?a=Fl([r,o]):this.mergeMode==="sum"?a=X(r,o):this.mergeMode==="ave"?a=D(.5,X(r,o)):this.mergeMode==="mul"?a=D(r,o):this.mergeMode==null&&(a=[r,o]),this.returnState?this.mergeMode==null?a.concat(i):[a].concat(i):a})}resetStates(t){this.forwardLayer.resetStates(),this.backwardLayer.resetStates()}build(t){os(this.forwardLayer.name,()=>{this.forwardLayer.build(t)}),os(this.backwardLayer.name,()=>{this.backwardLayer.build(t)}),this.built=!0}computeMask(t,e){Array.isArray(e)&&(e=e[0]);let s;if(this.returnSequences?this.mergeMode==null?s=[e,e]:s=e:this.mergeMode==null?s=[null,null]:s=null,this.returnState){const o=this.forwardLayer.states.map(i=>null);return Array.isArray(s)?s.concat(o).concat(o):[s].concat(o).concat(o)}else return s}get trainableWeights(){return this.forwardLayer.trainableWeights.concat(this.backwardLayer.trainableWeights)}get nonTrainableWeights(){return this.forwardLayer.nonTrainableWeights.concat(this.backwardLayer.nonTrainableWeights)}setFastWeightInitDuringBuild(t){super.setFastWeightInitDuringBuild(t),this.forwardLayer!=null&&this.forwardLayer.setFastWeightInitDuringBuild(t),this.backwardLayer!=null&&this.backwardLayer.setFastWeightInitDuringBuild(t)}getConfig(){const t={mergeMode:this.mergeMode},e=super.getConfig();return Object.assign(t,e),t}static fromConfig(t,e){const s=cn(e.layer);if(delete e.layer,e.numConstants!=null)throw new ut("Deserialization of a Bidirectional layer with numConstants present is not supported yet.");const r=e;return r.layer=s,new t(r)}}Lp.className="Bidirectional",H(Lp);/**
 * @license
 * Copyright 2022 CodeSmith LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class Op extends pt{constructor(t){super(t),this.scale=t.scale,t.offset?this.offset=t.offset:this.offset=0}getConfig(){const t={scale:this.scale,offset:this.offset},e=super.getConfig();return Object.assign(t,e),t}call(t,e){return z(()=>(t=ct(t),t.dtype!=="float32"&&(t=on(t,"float32")),X(D(t,this.scale),this.offset)))}}Op.className="Rescaling",H(Op);/**
 * @license
 * Copyright 2022 CodeSmith LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */const{resizeBilinear:Zv,cropAndResize:Jv}=bn;class _p extends pt{constructor(t){super(t),this.height=t.height,this.width=t.width}centerCrop(t,e,s,r,o,i,a,l){return z(()=>{let c,u=!1;const h=e/i,d=s/a,f=(r+e)/i,p=(o+s)/a,g=[h,d,f,p],m=[];t.rank===3?(u=!0,c=An([t])):c=t;for(let I=0;I<c.shape[0];I++)m.push(g);const b=Xs(m,[m.length,4]),y=rr(0,m.length,1,"int32"),w=Jv(c,b,y,[r,o],"nearest");return on(u?ct(Ts(w)):w,l)})}upsize(t,e,s,r){return z(()=>{const o=Zv(t,[e,s]);return on(o,r)})}call(t,e){return z(()=>{const s=ct(t),r=s.dtype,o=s.shape,i=o[o.length-3],a=o[o.length-2];let l=0;i!==this.height&&(l=Math.floor((i-this.height)/2));let c=0;return a!==this.width&&(c=Math.floor((a-this.width)/2),c===0&&(c=1)),l>=0&&c>=0?this.centerCrop(s,l,c,this.height,this.width,i,a,r):this.upsize(t,this.height,this.width,r)})}getConfig(){const t={height:this.height,width:this.width},e=super.getConfig();return Object.assign(t,e),t}computeOutputShape(t){t=yt(t);const e=t.length-3,s=t.length-2;return t[e]=this.height,t[s]=this.width,t}}_p.className="CenterCrop",H(_p);/**
 * @license
 * Copyright 2022 CodeSmith LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */function Yv(n,t,e,s){let r=ct(n);if(r.dtype!=="int32"&&(r=on(r,"int32")),t==="int")return r;const o=r.shape;if(r.rank===0&&(r=we(r,-1)),t==="oneHot"&&r.shape[r.shape.length-1]!==1&&(r=we(r,-1)),r.rank>2)throw new A(`When outputMode is not int, maximum output rank is 2 Received outputMode ${t} and input shape ${o} which would result in output rank ${r.rank}.`);const i=["multiHot","oneHot"].includes(t),a=r;let l;if(typeof s<"u"&&t==="count"?l=eh(a,s,e,i):l=eh(a,[],e,i),t!=="tfIdf")return l;if(s)return D(l,s);throw new A("When outputMode is 'tfIdf', weights must be provided.")}/**
 * @license
 * Copyright 2022 CodeSmith LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class Bp extends pt{constructor(t){super(t),this.numTokens=t.numTokens,t.outputMode?this.outputMode=t.outputMode:this.outputMode="multiHot"}getConfig(){const t={numTokens:this.numTokens,outputMode:this.outputMode},e=super.getConfig();return Object.assign(t,e),t}computeOutputShape(t){return t=yt(t),t==null?[this.numTokens]:this.outputMode==="oneHot"&&t[t.length-1]!==1?(t.push(this.numTokens),t):(t[t.length-1]=this.numTokens,t)}call(t,e){return z(()=>{t=ct(t),t.dtype!=="int32"&&(t=on(t,"int32"));let s;if(typeof e.countWeights<"u"){if(this.outputMode!=="count")throw new A(`countWeights is not used when outputMode !== count.
              Received countWeights=${e.countWeights}`);s=ct(e.countWeights)}const r=Qe(t),o=ll(t),i=Ae(this.numTokens,r).bufferSync().get(0),a=vs(o,0).bufferSync().get(0);if(!(i&&a))throw new A(`Input values must be between 0 < values <= numTokens with numTokens=${this.numTokens}`);return Yv(t,this.outputMode,this.numTokens,s)})}}Bp.className="CategoryEncoding",H(Bp);/**
 * @license
 * Copyright 2022 CodeSmith LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */const Qv=["bilinear","nearest"],Pp=new Set(Qv);class Wp extends pt{constructor(t){if(super(t),this.height=t.height,this.width=t.width,t.interpolation)if(Pp.has(t.interpolation))this.interpolation=t.interpolation;else throw new A(`Invalid interpolation parameter: ${t.interpolation} is not implemented`);else this.interpolation="bilinear";this.cropToAspectRatio=!!t.cropToAspectRatio}computeOutputShape(t){t=yt(t);const e=t[2];return[this.height,this.width,e]}getConfig(){const t={height:this.height,width:this.width,interpolation:this.interpolation,cropToAspectRatio:this.cropToAspectRatio},e=super.getConfig();return Object.assign(t,e),t}call(t,e){return z(()=>{const s=[this.height,this.width];if(this.interpolation==="bilinear")return bn.resizeBilinear(t,s,!this.cropToAspectRatio);if(this.interpolation==="nearest")return bn.resizeNearestNeighbor(t,s,!this.cropToAspectRatio);throw new Error(`Interpolation is ${this.interpolation} but only ${[...Pp]} are supported`)})}}Wp.className="Resizing",H(Wp);/**
 * @license
 * Copyright 2023 CodeSmith LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class Vp{constructor(t){this.seed=t}next(){if(this.seed!==void 0)return this.seed++}}Vp.className="RandomSeed";/**
 * @license
 * Copyright 2023 CodeSmith LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */class Gp extends pt{constructor(t){super(t),this.randomGenerator=new Vp(t.seed)}getConfig(){const t={seed:this.randomGenerator.seed},e=super.getConfig();return Object.assign(t,e),t}}Gp.className="BaseRandomLayer";/**
 * @license
 * Copyright 2023 CodeSmith LLC
 *
 * Use of this source code is governed by an MIT-style
 * license that can be found in the LICENSE file or at
 * https://opensource.org/licenses/MIT.
 * =============================================================================
 */const tN=["bilinear","nearest"],Up=new Set(tN);class Hp extends Gp{constructor(t){super(t);const{factor:e,interpolation:s="bilinear"}=t;if(this.factor=e,Array.isArray(this.factor)&&this.factor.length===2)this.widthLower=this.factor[0],this.widthUpper=this.factor[1];else if(!Array.isArray(this.factor)&&this.factor>0)this.widthLower=-this.factor,this.widthUpper=this.factor;else throw new A(`Invalid factor: ${this.factor}. Must be positive number or tuple of 2 numbers`);if(this.widthLower<-1||this.widthUpper<-1)throw new A(`factor must have values larger than -1. Got: ${this.factor}`);if(this.widthUpper<this.widthLower)throw new A(`factor cannot have upper bound less than lower bound.
        Got upper bound: ${this.widthUpper}.
        Got lower bound: ${this.widthLower}
      `);if(s)if(Up.has(s))this.interpolation=s;else throw new A(`Invalid interpolation parameter: ${s} is not implemented`)}getConfig(){const t={factor:this.factor,interpolation:this.interpolation},e=super.getConfig();return Object.assign(t,e),t}computeOutputShape(t){t=yt(t);const e=t[2];return[this.imgHeight,-1,e]}call(t,e){return z(()=>{const s=ct(t);this.imgHeight=s.shape[s.shape.length-3];const r=s.shape[s.shape.length-2];this.widthFactor=sr([1],1+this.widthLower,1+this.widthUpper,"float32",this.randomGenerator.next());let o=this.widthFactor.dataSync()[0]*r;o=Math.round(o);const i=[this.imgHeight,o];switch(this.interpolation){case"bilinear":return bn.resizeBilinear(t,i);case"nearest":return bn.resizeNearestNeighbor(t,i);default:throw new Error(`Interpolation is ${this.interpolation}
          but only ${[...Up]} are supported`)}})}}Hp.className="RandomWidth",H(Hp);/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function et(n,t){Array.isArray(n)||(n=[n]),n.forEach(e=>{e!=null&&v(e.dtype!=="complex64",()=>`${t} does not support complex64 tensors in the CPU backend.`)})}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const eN=Uw;class li extends wc{nextDataId(){return li.nextDataId++}constructor(){super(),this.blockSize=48,this.firstUse=!0,this.data=new Nm(this,_u())}write(t,e,s){this.firstUse&&(this.firstUse=!1,gt().get("IS_NODE")&&In(`
============================
Hi, looks like you are running TensorFlow.js in Node.js. To speed things up dramatically, install our node backend, visit https://github.com/tensorflow/tfjs-node for more details. 
============================`));const r={id:this.nextDataId()};return this.data.set(r,{values:t,dtype:s,refCount:1}),r}makeTensorInfo(t,e,s){let r;if(e==="string"&&s!=null&&s.length>0&&Cr(s[0])){const o=s.map(i=>Xn(i));r=this.write(o,t,e)}else r=this.write(s,t,e);return{dataId:r,shape:t,dtype:e}}refCount(t){return this.data.has(t)?this.data.get(t).refCount:0}incRef(t){const e=this.data.get(t);e.refCount++}decRef(t){if(this.data.has(t)){const e=this.data.get(t);e.refCount--}}move(t,e,s,r,o){this.data.set(t,{values:e,dtype:r,refCount:o})}numDataIds(){return this.data.numDataIds()}async read(t){return this.readSync(t)}readSync(t){const{dtype:e,complexTensorInfos:s}=this.data.get(t);if(e==="complex64"){const r=this.readSync(s.real.dataId),o=this.readSync(s.imag.dataId);return Ds(r,o)}return Rm(this.data.get(t).values,e)}bufferSync(t){const e=this.readSync(t.dataId);if(t.dtype==="string")try{const s=e.map(r=>Us(r));return mt(t.shape,t.dtype,s)}catch{throw new Error("Failed to decode encoded string bytes into utf-8")}return mt(t.shape,t.dtype,e)}makeOutput(t,e,s){return _u().makeTensorFromTensorInfo(this.makeTensorInfo(e,s,t),this)}disposeData(t,e=!1){if(this.data.has(t)){if(this.data.get(t).refCount--,!e&&this.data.get(t).refCount>0)return!1;const{complexTensorInfos:s}=this.data.get(t);s!=null&&(this.disposeData(s.real.dataId,!0),this.disposeData(s.imag.dataId,!0)),this.data.delete(t)}return!0}disposeIntermediateTensorInfo(t){this.disposeData(t.dataId)}async time(t){const e=vn();return t(),{kernelMs:vn()-e}}memory(){return{unreliable:!0,reasons:["The reported memory is an upper bound. Due to automatic garbage collection, the true allocated memory may be less."]}}where(t){et([t],"where");const e=this.readSync(t.dataId);return eN(t.shape,e)}dispose(){}floatPrecision(){return 32}epsilon(){return super.epsilon()}}li.nextDataId=0;/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function nN(n){const t=new Float32Array(n.length);for(let e=0;e<n.length;++e)t[e]=Math.abs(n[e]);return t}const sN={kernelName:Ni,backendName:"cpu",kernelFunc:n=>{const{x:t}=n.inputs,e=n.backend;et(t,"abs");let s=new Float32Array(Z(t.shape));const r=e.data.get(t.dataId).values;return s=nN(r),e.makeOutput(s,t.shape,t.dtype)}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Vt(n){return(t,e,s,r,o)=>{const i=Ct(t,e),a=i.length,l=it(i),c=Z(i),u=he(o,c),h=t.length,d=e.length,f=it(t),p=it(e),g=vo(t,i),m=vo(e,i);if(g.length+m.length===0)for(let b=0;b<u.length;++b)u[b]=n(s[b%s.length],r[b%r.length]);else for(let b=0;b<u.length;++b){const y=fs(b,a,l),k=y.slice(-h);g.forEach(T=>k[T]=0);const w=je(k,h,f),I=y.slice(-d);m.forEach(T=>I[T]=0);const S=je(I,d,p);u[b]=n(s[w],r[S])}return[u,i]}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ie(n){const{inputs:t,backend:e}=n,{real:s,imag:r}=t,o=e.data.get(s.dataId).values,i=e.data.get(r.dataId).values,a=e.makeTensorInfo(s.shape,"complex64"),l=e.data.get(a.dataId);return l.complexTensorInfos={real:e.makeTensorInfo(s.shape,"float32",o),imag:e.makeTensorInfo(r.shape,"float32",i)},a}const rN={kernelName:zc,backendName:"cpu",kernelFunc:Ie};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function ci(n,t,e="float32"){if(e==="complex64"){const r=ci(n,t,"float32"),o=ci(n,t,"float32");return Ie({inputs:{real:r,imag:o},backend:n})}const s=ie(Z(t),e);return n.makeTensorInfo(t,e,s)}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function hn(n){const{inputs:t,backend:e}=n,{x:s}=t;return e.incRef(s.dataId),{dataId:s.dataId,shape:s.shape,dtype:s.dtype}}const oN={kernelName:Pr,backendName:"cpu",kernelFunc:hn};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function cs(n){const{inputs:t,backend:e}=n,{input:s}=t,r=e.data.get(s.dataId).complexTensorInfos.real,o=e.data.get(r.dataId).values;return e.makeTensorInfo(r.shape,r.dtype,o)}const iN={kernelName:au,backendName:"cpu",kernelFunc:cs};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function aN(n,t,e,s){if(s==="int32"){const r=Int32Array.from(n);return[t,"int32",r]}if(s==="bool"){const r=Kn([0],e),[o,i]=Vt((a,l)=>a!==l?1:0)(t,[],n,r,"bool");return[i,"bool",o]}throw new Error(`Error in Cast: failed to cast ${e} to ${s}`)}function Bn(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{dtype:o}=s;if(o==="complex64"){if(r.dtype==="complex64")return hn({inputs:{x:r},backend:e});const u=ci(e,r.shape,r.dtype),h=Bn({inputs:{x:r},backend:e,attrs:{dtype:"float32"}}),d=Ie({inputs:{real:h,imag:u},backend:e});return e.disposeIntermediateTensorInfo(u),e.disposeIntermediateTensorInfo(h),d}if(r.dtype==="complex64"){const u=cs({inputs:{input:r},backend:e}),h=Bn({inputs:{x:u},backend:e,attrs:{dtype:o}});return e.disposeIntermediateTensorInfo(u),h}if(!Dm(r.dtype,o)){const u=hn({inputs:{x:r},backend:e});return{dataId:u.dataId,shape:u.shape,dtype:o}}const i=e.data.get(r.dataId).values,[a,l,c]=aN(i,r.shape,r.dtype,o);return e.makeTensorInfo(a,l,c)}const lN={kernelName:Ar,backendName:"cpu",kernelFunc:Bn};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Xt(n,t,e,s){return e==null?({inputs:r,backend:o})=>{const{a:i,b:a}=r,l=o;et([i,a],n);const c=l.data.get(i.dataId).values,u=l.data.get(a.dataId).values,h=i.dtype==="string"?or(c):c,d=i.dtype==="string"?or(u):u,f=s||i.dtype,[p,g]=t(i.shape,a.shape,h,d,f);return l.makeTensorInfo(g,f,p)}:({inputs:r,backend:o})=>{const{a:i,b:a}=r,l=o;if(i.dtype==="complex64"||a.dtype==="complex64"){const c=Bn({inputs:{x:i},backend:l,attrs:{dtype:"complex64"}}),u=l.data.get(c.dataId),h=u.complexTensorInfos.real,d=u.complexTensorInfos.imag,f=l.data.get(h.dataId).values,p=l.data.get(d.dataId).values,g=Bn({inputs:{x:a},backend:l,attrs:{dtype:"complex64"}}),m=l.data.get(g.dataId),b=m.complexTensorInfos.real,y=m.complexTensorInfos.imag,k=l.data.get(b.dataId).values,w=l.data.get(y.dataId).values,[I,S,T]=e(i.shape,a.shape,f,p,k,w),C=l.makeTensorInfo(T,"float32",I),N=l.makeTensorInfo(T,"float32",S),$=Ie({inputs:{real:C,imag:N},backend:l});return l.disposeIntermediateTensorInfo(c),l.disposeIntermediateTensorInfo(g),l.disposeIntermediateTensorInfo(C),l.disposeIntermediateTensorInfo(N),$}else{const c=l.data.get(i.dataId).values,u=l.data.get(a.dataId).values,h=s||i.dtype,[d,f]=t(i.shape,a.shape,c,u,h);return l.makeTensorInfo(f,h,d)}}}function cc(n){return(t,e,s,r,o,i)=>{const a=Ct(t,e),l=Z(a),c=a.length,u=it(a),h=he("float32",l),d=he("float32",l),f=vo(t,a),p=vo(e,a),g=Ds(s,r),m=Ds(o,i),b=t.length,y=it(t),k=e.length,w=it(e);if(f.length+p.length===0)for(let I=0;I<h.length;I++){const S=I%g.length,T=I%m.length,C=n(g[S*2],g[S*2+1],m[T*2],m[T*2+1]);h[I]=C.real,d[I]=C.imag}else for(let I=0;I<h.length;I++){const S=fs(I,c,u),T=S.slice(-b);f.forEach(F=>T[F]=0);const C=je(T,b,y),N=S.slice(-k);p.forEach(F=>N[F]=0);const $=je(N,k,w),x=n(g[C*2],g[C*2+1],m[$*2],m[$*2+1]);h[I]=x.real,d[I]=x.imag}return[h,d,a]}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const cN=Vt(((n,t)=>n+t)),uN=cc(((n,t,e,s)=>({real:n+e,imag:t+s}))),Os=Xt(Vs,cN,uN),hN={kernelName:Vs,backendName:"cpu",kernelFunc:Os};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function qp(n,t,e,s,r){const o=Z(s),i=ie(r,e);for(let a=0;a<n.length;a++){const l=n[a];if(l<0)throw new Error("Input x must be non-negative!");l>=r||(o>0?i[l]+=t[a]:i[l]+=1)}return i}function dN(n,t,e,s=!1){const r=n.shape[0],o=n.shape[1],i=mt([r,e],t.dtype);for(let a=0;a<r;a++)for(let l=0;l<o;l++){const c=n.get(a,l);if(c<0)throw new Error("Input x must be non-negative!");c>=e||(s?i.set(1,a,c):t.size>0?i.set(i.get(a,c)+t.get(a,l),a,c):i.set(i.get(a,c)+1,a,c))}return i}/**
 * @license
 * Copyright 2023 Google LLC.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const fN=Vt(((n,t)=>n&t)),pN=Xt(Rc,fN),mN={kernelName:Rc,backendName:"cpu",kernelFunc:pN};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Pn(n){return(t,e,s)=>{const r=Gt(e,t.length);for(let o=0;o<t.length;++o)r[o]=n(t[o],s);return r}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function It(n,t,e){const s=Pn(t);return Wn(n,s,e)}function Wn(n,t,e){return({inputs:s,attrs:r,backend:o})=>{const{x:i}=s;et(i,n);const a=o,l=a.data.get(i.dataId).values;let c;if(i.dtype==="string"){if(!Array.isArray(l))throw new Error("String tensor's value was not an instance of Array");c=or(l)}else c=l;const u=e||i.dtype,h=t(c,u,r);return a.makeTensorInfo(i.shape,u,h)}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const gN=Pn(n=>Math.ceil(n)),bN=Wn(_i,gN),yN={kernelName:_i,backendName:"cpu",kernelFunc:bN};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function wN(n,t,e,s){const r=Gt(e,Z(t));if(s&&e!=="string"){let o=0;n.forEach(i=>{const a=Z(i.shape);r.set(i.vals,o),o+=a})}else{let o=0;n.forEach(i=>{const a=e==="string"?or(i.vals):i.vals;let l=0;for(let c=0;c<i.shape[0];++c){const u=c*t[1]+o;for(let h=0;h<i.shape[1];++h)r[u+h]=a[l++]}o+=i.shape[1]})}return r}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const kN=Vt((n,t)=>n===t?1:0),jp=Xt(Ki,kN,null,"bool"),xN={kernelName:Ki,backendName:"cpu",kernelFunc:jp};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const IN=Pn(n=>Math.exp(n)),Kp=Wn(Lr,IN,"float32"),SN={kernelName:Lr,backendName:"cpu",kernelFunc:Kp};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const vN=Pn(n=>Math.expm1(n)),NN=Wn(Zi,vN),$N={kernelName:Zi,backendName:"cpu",kernelFunc:NN};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const TN=Pn(n=>Math.floor(n)),CN=Wn(Or,TN),AN={kernelName:Or,backendName:"cpu",kernelFunc:CN};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const EN=Vt((n,t)=>Math.floor(n/t)),DN=Xt(_r,EN,null,"int32"),FN={kernelName:_r,backendName:"cpu",kernelFunc:DN};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function MN(n,t,e,s,r,o,i,a,l){const c=mt([s,o],e);for(let u=0;u<s;u++){const h=[];let d=0;for(let f=0;f<r;f++){const p=n[u*r+f];d+=p*i[f],h.push(p)}if(d<0||d>=l/o)throw new Error(`Invalid indices: ${h} does not index into ${a}`);for(let f=0;f<o;f++)c.values[u*o+f]=t.get(...t.indexToLoc(d*o+f))}return c}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function RN(n,t,e){const s=mt(e,n.dtype);for(let r=0;r<s.size;++r){const i=s.indexToLoc(r).slice(),a=i[0],l=i[2],c=t.locToIndex([a,l]);i[2]=t.values[c];const u=n.locToIndex(i);0<=u&&u<n.values.length&&(s.values[r]=n.values[u])}return s}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const zN=Vt((n,t)=>n>t?1:0),LN=Xt(Qi,zN,null,"bool"),ON={kernelName:Qi,backendName:"cpu",kernelFunc:LN};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const _N=Vt((n,t)=>n>=t?1:0),BN=Xt(Br,_N,null,"bool"),PN={kernelName:Br,backendName:"cpu",kernelFunc:BN};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const WN=Vt((n,t)=>n<t?1:0),VN=Xt(ra,WN,null,"bool"),GN={kernelName:ra,backendName:"cpu",kernelFunc:VN};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const UN=Vt((n,t)=>n<=t?1:0),HN=Xt(oa,UN,null,"bool"),qN={kernelName:oa,backendName:"cpu",kernelFunc:HN};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function jN(n,t,e){const s=(t-n)/(e-1),r=ie(e,"float32");r[0]=n;for(let o=1;o<r.length;o++)r[o]=r[o-1]+s;return r}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const KN=Pn(n=>Math.log(n)),XN=Wn(Wr,KN),ZN={kernelName:Wr,backendName:"cpu",kernelFunc:XN};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function JN(n,t,e,s){const r=he(s,Z(e));for(let o=0;o<r.length;++o){const i=o*t;let a=n[i];for(let l=0;l<t;++l){const c=n[i+l];(Number.isNaN(c)||c>a)&&(a=c)}r[o]=a}return r}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const YN=Vt(((n,t)=>Math.max(n,t))),QN=Xt(Gr,YN),t2={kernelName:Gr,backendName:"cpu",kernelFunc:QN};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const e2=Vt(((n,t)=>Math.min(n,t))),n2=Xt(Ur,e2),s2={kernelName:Ur,backendName:"cpu",kernelFunc:n2};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Xp=Vt(((n,t)=>n*t)),r2=cc(((n,t,e,s)=>({real:n*e-t*s,imag:n*s+t*e}))),ui=Xt(Hr,Xp,r2),o2={kernelName:Hr,backendName:"cpu",kernelFunc:ui};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function i2(n,t,e){const s=Ga(-1,e);return Xp([],t,s,n,e)}function a2(n){const{inputs:t,backend:e}=n,{x:s}=t;et(s,"neg");const r=e.data.get(s.dataId).values,[o,i]=i2(r,s.shape,s.dtype);return e.makeTensorInfo(i,s.dtype,o)}const l2={kernelName:pa,backendName:"cpu",kernelFunc:a2};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const c2=Vt(((n,t)=>n!==t?1:0)),u2=Xt(ma,c2,null,"bool"),h2={kernelName:ma,backendName:"cpu",kernelFunc:u2};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Zp(n,t,e,s,r){const o=t.length,i=Z(t),a=it(t),l=it(r),c=he(e,Z(r));for(let u=0;u<i;++u){const h=fs(u,o,a),d=new Array(h.length);for(let p=0;p<d.length;p++)d[p]=h[s[p]];const f=je(d,o,l);c[f]=n[u]}return c}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function me(n){const{inputs:t,attrs:e,backend:s}=n,{x:r}=t,{perm:o}=e;et(r,"transpose");const i=r.shape.length,a=new Array(i);for(let h=0;h<a.length;h++)a[h]=r.shape[o[h]];const l=s.data.get(r.dataId).values,c=Zp(l,r.shape,r.dtype,o,a);return{dataId:s.write(c,a,r.dtype),shape:a,dtype:r.dtype}}const d2={kernelName:Gs,backendName:"cpu",kernelFunc:me};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function f2(n,t,e,s){const[r,o]=Je(n,s),i=ms(t,"int32"),a=ie(Z(r),i),l=Z(o);for(let c=0;c<a.length;++c){const u=c*l;let h=1;for(let d=0;d<l;++d)h*=e[u+d];a[c]=h}return{outVals:a,outShape:r,outDtype:i}}function p2(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{axis:o,keepDims:i}=s;et(r,"prod");const a=r.shape.length,l=Ft(o,r.shape),c=Ce(l,a);let u=l,h=r;const d=[];c!=null&&(h=me({inputs:{x:r},backend:e,attrs:{perm:c}}),d.push(h),u=Ye(u.length,a));const f=e.data.get(h.dataId).values,{outVals:p,outShape:g,outDtype:m}=f2(h.shape,h.dtype,f,u);let b=g;return i&&(b=Te(g,l)),d.forEach(y=>e.disposeIntermediateTensorInfo(y)),e.makeTensorInfo(b,m,p)}const m2={kernelName:ou,backendName:"cpu",kernelFunc:p2};/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function g2(n,t,e){n.forEach((s,r)=>{if(s<0||s>=e){const o=fs(r,t.length,it(t)).join(",");throw new Error(`indices[${o}] = ${s} is not in [0, ${e})`)}})}function b2(n,t){for(let e=0;e<n.length;++e){const s=n[e],r=e===n.length-1?t:n[e+1].length;if(s.length===0)throw new Error("Ragged splits may not be empty");if(s[0]<0)throw new Error("Ragged splits must be non-negative");if(s[s.length-1]>r)throw new Error("Ragged splits must not point past values");for(let o=1;o<s.length;++o)if(s[o-1]>s[o])throw new Error("Ragged splits must be sorted in ascending order")}}function y2(n,t,e,s){const r=[];let o=0;const i=t.length-1+e.length,a=new Array(i).fill(null).map(()=>[0]);b2(e,s);let l=1;for(let c=0;c<t.length-1;++c){l*=t[c];const u=t[c+1];for(let h=1;h<l+1;++h)a[c].push(h*u)}for(let c=0;c<n.length;++c){let u=n[c],h=n[c]+1;for(let d=0;d<e.length;++d){const f=e[d],p=d+t.length-1;if(p>=0){const g=a[p],m=g[g.length-1]-f[u];for(let b=u;b<h;++b)a[p].push(f[b+1]+m)}u=f[u],h=f[h]}h!==u&&(r.push([u,h]),o+=h-u)}return{outSplits:a,valueSlices:r,numValues:o}}function w2(n){const t=[];for(let e=0;e<n.length;++e){const s=n[e].length,r=Gt("int32",s);t.push(r),n[e].forEach((o,i)=>r[i]=o)}return t}function Jp(n,t){const e=n.slice(0,t);for(;e.length<t;)e.push(1);for(let s=t;s<n.length;s++)e[t-1]*=n[s];return e}function k2(n,t,e,s,r,o){const i=Jp(t,2)[1],a=Jp(o,2)[1];let l=0;for(const c of e)for(let u=c[0];u<c[1];++u){for(let h=0;h<s;++h)r[l*a+h]=n[u*i+h];++l}}function x2(n,t,e,s,r){const o=t.slice();o[0]=r;const i=Gt(e,Z(o)),a=n.length,l=a===0?0:a/t[0];return k2(n,t,s,l,i,o),[i,o]}function I2(n,t,e,s,r,o,i,a){if(n.length===0)throw new Error("paramsNestedSplits must be non empty");if(t[0].length===0)throw new Error("Split tensors must not be scalars");const l=t[0][0]-1;if(g2(o,i,l),s.length===0)throw new Error("params.rank must be nonzero");const c=s[0],{outSplits:u,valueSlices:h,numValues:d}=y2(o,i,n,c),f=w2(u),p=x2(e,s,r,h,d);return[f,p[0],p[1]]}/**
 * @license
 * Copyright 2022 Google LLC.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Yp=2147483647;function S2(n,t,e,s,r,o,i){if(t.length>1)throw new Error("starts must be a scalar or vector");if(r.length>1)throw new Error("limits must be a scalar or vector");if(i.length>1)throw new Error("deltas must be a scalar or vector");const a=t.length===0,l=r.length===0,c=i.length===0,u=[];a||u.push(t[0]),l||u.push(r[0]),c||u.push(i[0]);for(let m=1;m<u.length;++m)if(u[m]!==u[m-1])throw new Error("starts, limits, and deltas must have the same shape");const h=u.length===0?1:u[0],d=Gt("int32",h+1);d[0]=0;for(let m=0;m<h;++m){const b=a?n[0]:n[m],y=l?s[0]:s[m],k=c?o[0]:o[m];if(k===0)throw new Error("Requires delta != 0");let w;if(k>0&&y<b||k<0&&y>b)w=0;else if(w=Math.ceil(Math.abs((y-b)/k)),w>Yp)throw new Error(`Requires ((limit - start) / delta) <= ${Yp}`);d[m+1]=d[m]+w}const f=d[h],p=Gt(e,f);let g=0;for(let m=0;m<h;++m){const b=d[m+1]-d[m];let y=a?n[0]:n[m];const k=c?o[0]:o[m];for(let w=0;w<b;++w)p[g++]=y,y+=k}return[d,p]}/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */var ze=nn;class hi{constructor(t,e,s,r,o,i,a,l,c,u){this.shape=t,this.shapeShape=e,this.values=s,this.valuesShape=r,this.valuesDType=o,this.defaultValue=i,this.defaultValueShape=a,this.rowPartitionValues=l,this.rowPartitionValuesShapes=c,this.rowPartitionTypes=gk(u),this.raggedRank=bk(this.rowPartitionTypes)}getRowPartitionTypeByDimension(t){return this.rowPartitionTypes[0]===ze.FIRST_DIM_SIZE?this.rowPartitionTypes[t+1]:this.rowPartitionTypes[t]}getRowPartitionTensor(t){return this.rowPartitionTypes[0]===ze.FIRST_DIM_SIZE?this.rowPartitionValues[t+1]:this.rowPartitionValues[t]}getMaxWidth(t){const e=this.getRowPartitionTensor(t-1);switch(this.getRowPartitionTypeByDimension(t-1)){case ze.VALUE_ROWIDS:return hi.getMaxWidthValueRowID(e);case ze.ROW_SPLITS:return hi.getMaxWidthRowSplit(e);default:throw new Error(`Cannot handle partition type ${ze[this.getRowPartitionTypeByDimension(t-1)]}`)}}static getMaxWidthRowSplit(t){const e=t.length;if(e===0||e===1)return 0;let s=0;for(let r=0;r<e-1;++r){const o=t[r+1]-t[r];o>s&&(s=o)}return s}static getMaxWidthValueRowID(t){const e=t.length;if(e===0)return 0;let s=0,r=t[0],o=0;for(let i=1;i<e;++i){const a=t[i];a!==r&&(r=a,o=Math.max(i-s,o),s=i)}return Math.max(e-s,o)}tensorShapeFromTensor(t,e,s=!0){if(e.length===0){if(t[0]===-1)return[];throw new Error("The only valid scalar shape tensor is the fully unknown shape specified as -1.")}return tm(t,s)}calculateOutputSize(t){const e=this.valuesShape,s=this.defaultValueShape;yk(s,e);const r=this.tensorShapeFromTensor(this.shape,this.shapeShape),i=mk(this.raggedRank,r,e);i[0]<0&&(i[0]=t);for(let a=1;a<=this.raggedRank;++a)i[a]<0&&(i[a]=this.getMaxWidth(a));return i}calculateFirstParentOutputIndex(t,e,s){const r=Math.min(t,s),o=[];let i=0;for(let a=0;a<r;++a,i+=e)o.push(i);for(let a=r;a<t;++a)o.push(-1);return v(o.length===t,()=>"Final length of result must be equal to firstDimension."),o}calculateOutputIndexRowSplit(t,e,s,r){const o=t.length,i=[];for(let a=0;a<o-1;++a){const l=t[a+1]-t[a];let c=Math.min(r,l),u=e[a];u===-1&&(c=0);for(let h=0;h<c;++h)i.push(u),u+=s;for(let h=0;h<l-c;++h)i.push(-1)}if(o>0&&i.length!==t[o-1])throw new Error("Invalid row split size.");return i}calculateOutputIndexValueRowID(t,e,s,r){const o=t.length,i=[];if(o===0)return[];let a=0,l=t[0];if(l>=e.length)throw new Error(`Got currentValueRowId=${l}, which is not less than ${e.length}`);let c=e[l];i.push(c);for(let u=1;u<o;++u){const h=t[u];if(h===l)c>=0&&(++a,a<r?c+=s:c=-1);else{if(a=0,l=h,h>=e.length)throw new Error(`Got nextValueRowId=${h} which is not less than ${e.length}`);c=e[h]}i.push(c)}if(i.length!==t.length)throw new Error("Invalid row ids.");return i}calculateOutputIndex(t,e,s,r){const o=this.getRowPartitionTensor(t),i=this.getRowPartitionTypeByDimension(t);switch(i){case ze.VALUE_ROWIDS:return this.calculateOutputIndexValueRowID(o,e,s,r);case ze.ROW_SPLITS:if(o.length-1>e.length)throw new Error(`Row partition size is greater than output size: ${o.length-1} > ${e.length}`);return this.calculateOutputIndexRowSplit(o,e,s,r);default:throw new Error(`Unsupported partition type: ${ze[i]}`)}}getFirstDimensionSize(){const t=this.rowPartitionValues[0];if(this.rowPartitionTypes.length===0)throw new Error("No row_partition_types given.");const e=this.rowPartitionTypes[0];switch(e){case ze.FIRST_DIM_SIZE:return t[0];case ze.VALUE_ROWIDS:throw new Error("Cannot handle VALUE_ROWIDS in first dimension.");case ze.ROW_SPLITS:return this.rowPartitionValuesShapes[0][0]-1;default:throw new Error(`Cannot handle type ${ze[e]}`)}}compute(){if(this.rowPartitionValues[0].length<=0)throw new Error("Invalid first partition input. Tensor requires at least one element.");const e=this.getFirstDimensionSize(),s=this.calculateOutputSize(e),r=new Array(this.raggedRank+1);r[r.length-1]=1;for(let l=r.length-2;l>=0;--l)r[l]=r[l+1]*s[l+1];const o=tm(s,!1),i=Gt(this.valuesDType,Z(o));if(r[0]*s[0]>0){let l=this.calculateFirstParentOutputIndex(e,r[0],s[0]);for(let c=1;c<=this.raggedRank;++c)l=this.calculateOutputIndex(c-1,l,r[c],s[c]);this.setOutput(this.raggedRank,l,i,o)}return[o,i]}setOutput(t,e,s,r){if(s.length===0)return;const o=this.values,i=s;let a=r.slice();a=a.slice(t+1);const l=Z(a),c=e.length;let u=this.defaultValue;if(u.length!==l&&u.length!==1){const p=this.defaultValueShape;z(()=>{const g=_(u,p);u=Io(g,a).dataSync()})}let h=0,d=0,f=0;for(let p=0;p<=c;++p){let g=p<c?e[p]:-1;if(g===f){++f;continue}if(d<f){const m=o.subarray(h*l),b=i.subarray(d*l),y=(f-d)*l;Qp(b,m,y)}if(p>=c){const m=s.length;g=Math.floor(m/l)}if(g>f)if(this.defaultValue.length===1)i.subarray(f*l,g*l).fill(this.defaultValue[0]),f=g;else for(;g>f;){const m=i.slice(f*l);Qp(m,u,l),++f}g<0?(h=p+1,d=f):(h=p,d=f,f=d+1)}}}function Qp(n,t,e){for(let s=0;s<e;s++)n[s]=t[s]}function tm(n,t){const e=[];for(let s of n){if(s<0){if(!t)throw new Error(`Dimension ${s} must be >= 0`);if(s<-1)throw new Error(`Dimension ${s} must be >= -1`);s=-1}e.push(s)}return e}function v2(n,t,e,s,r,o,i,a,l,c){return new hi(n,t,e,s,r,o,i,a,l,c).compute()}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function N2(n,t,e,s){const r=n===t,o=n<t&&e<0,i=t<n&&e>1;if(r||o||i)return ie(0,s);const a=Math.abs(Math.ceil((t-n)/e)),l=ie(a,s);t<n&&e===1&&(e=-1),l[0]=n;for(let c=1;c<l.length;c++)l[c]=l[c-1]+e;return l}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const $2=Pn(n=>1/Math.sqrt(n)),T2=Wn(Zr,$2),C2={kernelName:Zr,backendName:"cpu",kernelFunc:T2};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function _s(n,t,e,s,r,o,i,a,l,c){const u=[s/r,r],h=n.values,d=t.values;if(s===0)return mt(e,t.dtype);const f=l instanceof te?l:mt(u,t.dtype);typeof l=="string"||typeof l=="number"?f.values.fill(l):typeof l=="boolean"&&f.values.fill(+l);for(let p=0;p<o;p++){const g=[];let m=0;for(let b=0;b<i;b++){const y=h[p*i+b];g.push(y),m+=y*a[b]}if(m<0||m>=s/r)throw new Error(`Invalid indices: ${g} does not index into ${e}`);for(let b=0;b<r;b++)c?f.values[m*r+b]+=d[p*r+b]:f.values[m*r+b]=t.rank===0?d[0]:d[p*r+b]}return f}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const em=It(to,n=>1/(1+Math.exp(-n))),A2={kernelName:to,backendName:"cpu",kernelFunc:em};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function E2(n,t,e,s,r){const o=ak(s,t,e),i=Z(e),a=it(s);if(o){const h=lk(t,a);return r==="string"?n.slice(h,h+i):n.subarray(h,h+i)}const l=r==="string"?or(n):n,c=mt(s,r,l),u=mt(e,r);for(let h=0;h<u.size;++h){const d=u.indexToLoc(h),f=d.map((p,g)=>p+t[g]);u.set(c.get(...f),...d)}return r==="string"?tx(u.values):u.values}function us(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{begin:o,size:i}=s;et(r,"slice");const[a,l]=Gh(r,o,i);ok(r,a,l);const c=e.data.get(r.dataId).values,u=E2(c,a,l,r.shape,r.dtype);return e.makeTensorInfo(l,r.dtype,u)}const D2={kernelName:Ta,backendName:"cpu",kernelFunc:us};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function F2(n,t,e,s,r,o,i){const a=t[0],l=o[0],c=new Array(l),u=new Array(a),h=t[1];if(l===0){if(a!==0)throw new Error(Vk(a));const m=Gt(e,0),b=Gt(r,0);return[m,[0,h],b,c,u]}let d=!0,f=0;const p=new Array(l).fill(0);for(let m=0;m<a;++m){const b=n[m*h];if(b<0)throw new Error(Gk(m,b));if(b>=l)throw new Error(Uk(m,b,l));++p[b],d=d&&b>=f,f=b}let g=!0;for(let m=0;m<l;++m){const b=p[m]===0;c[m]=b,g=g&&!b,p[m]=Math.max(p[m],1),m>0&&(p[m]+=p[m-1])}if(g&&d){const m=n,b=s;for(let y=0;y<a;++y)u[y]=y;return[m,[a,h],b,c,u]}else{const m=p[l-1],b=Gt(e,m*h),y=Gt(r,m),k=new Array(l).fill(0);for(let w=0;w<a;++w){const I=n[w*h],S=k[I],T=(I===0?0:p[I-1])+S;k[I]++;for(let C=0;C<h;++C)b[T*h+C]=n[w*h+C];y[T]=s[w],u[w]=T}for(let w=0;w<l;++w)if(k[w]===0){const S=w===0?0:p[w-1];b[S*h+0]=w;for(let T=1;T<h;++T)b[S*h+T]=0;y[S]=i}return[b,[m,h],y,c,u]}}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function M2(n,t,e,s,r){const o=Z(s),i=t[0],a=r.length,l=[];let c=1,u=-1;for(let m=0;m<a;++m){const b=r[m];if(b===-1){if(u!==-1)throw new Error(Hk(u,m));u=m,l.push(1)}else{if(b<0)throw new Error(qk(m,b));c*=b,l.push(b)}}if(u!==-1){if(c<=0)throw new Error(jk());const m=Math.trunc(o/c);if(c*m!==o)throw new Error(Kk(s,l));l[u]=m}if(Z(l)!==o)throw new Error(Xk(s,l));const d=s.length,f=[];if(d>0){f[d-1]=1;for(let m=d-2;m>=0;--m)f[m]=f[m+1]*s[m+1]}const p=[];if(a>0){p[a-1]=1;for(let m=a-2;m>=0;--m)p[m]=p[m+1]*l[m+1]}const g=Gt(e,i*a);for(let m=0;m<i;++m){let b=0;for(let y=0;y<d;++y)b+=n[m*d+y]*f[y];for(let y=0;y<a;++y)g[m*a+y]=Math.trunc(b/p[y]),b%=p[y]}return[g,[i,a],l]}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function nm(n,t,e,s,r,o=!1,i=0){const a=s.length,l=[t[0],n.length/t[0]],c=l[1],h=a>0?r[a-1]+1:0;if(h<0)throw new Error(Qh());const d=t.slice();d[0]=h;const f=d.reduce((k,w)=>k*w,1),p=Gt(e,f);if(a===0)return h>0&&p.fill(i),[p,d];if(h<=0)throw new Error(Qh());let g=0,m=1,b=0,y=r[g];for(;;){let k=0;if(m<a){if(k=r[m],y===k){++m;continue}if(y>=k)throw new Error(Zk())}if(y<0||y>=h)throw new Error(Jk(y,h));y>b&&p.fill(i,b*c,y*c);for(let w=g;w<m;++w){const I=s[w];if(I<0||I>=l[0])throw new Error(Yk(w,s[w],l[0]));for(let S=0;S<c;S++)p[y*c+S]+=n[I*c+S]}if(o)for(let w=0;w<c;w++)p[y*c+w]/=m-g;if(g=m,++m,b=y+1,y=k,m>a)break}return b<h&&p.fill(i,b*c,h*c),[p,d]}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const R2=It(no,n=>Math.sqrt(n)),z2={kernelName:no,backendName:"cpu",kernelFunc:R2};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const L2=Vt(((n,t)=>{const e=n-t;return e*e})),O2=Xt(Ma,L2),_2={kernelName:Ma,backendName:"cpu",kernelFunc:O2};/**
 * @license
 * Copyright 2023 Google LLC.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const B2=Pn((n,t)=>{const{pattern:e,replaceGlobal:s,rewrite:r}=t;return n.replace(new RegExp(e,s?"g":""),r)}),P2=Wn(hu,B2),W2={kernelName:hu,backendName:"cpu",kernelFunc:P2};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function V2(n,t,e,s){const r=mt(n,t.dtype);for(let o=0;o<r.size;o++){const i=r.indexToLoc(o),a=new Array(i.length);for(let l=0;l<a.length;l++)a[l]=i[l]*e[l]+s[l];r.set(t.get(...a),...i)}return r}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */class G2{constructor(t,e,s,r,o,i){this.separator=Xn(t),this.nGramWidths=e,this.leftPad=Xn(s),this.rightPad=Xn(r),this.padWidth=o,this.preserveShort=i}getPadWidth(t){return Math.min(this.padWidth<0?t-1:this.padWidth,t-1)}getNumNGrams(t,e){const s=this.getPadWidth(e);return Math.max(0,t+2*s-e+1)}createNGrams(t,e,s,r,o,i){for(let a=0;a<o;++a){const l=this.getPadWidth(i),c=Math.max(0,l-a),u=Math.max(0,l-(o-(a+1))),h=i-(c+u),d=e+(c>0?0:a-l);let f=0;f+=c*this.leftPad.length;for(let y=0;y<h;++y)f+=t[d+y].length;f+=u*this.rightPad.length;const p=c+u+h-1;f+=p*this.separator.length,s[r+a]=new Uint8Array(f);const g=s[r+a];let m=0;const b=y=>y.forEach(k=>g[m++]=k);for(let y=0;y<c;++y)b(this.leftPad),b(this.separator);for(let y=0;y<h-1;++y)b(t[d+y]),b(this.separator);if(h>0){b(t[d+h-1]);for(let y=0;y<u;++y)b(this.separator),b(this.rightPad)}else{for(let y=0;y<u-1;++y)b(this.rightPad),b(this.separator);b(this.rightPad)}}}compute(t,e){const s=t.length,r=e.length;if(r>0){let l=e[0];if(l!==0)throw new Error(`First split value must be 0, got ${l}`);for(let c=1;c<r;++c){let u=e[c]>=l;if(u=u&&e[c]<=s,!u)throw new Error(`Invalid split value ${e[c]}, must be in [${l}, ${s}]`);l=e[c]}if(l!==s)throw new Error(`Last split value must be data size. Expected ${s}, got ${l}`)}const o=r-1,i=Gt("int32",r);if(s===0||r===0){const l=new Array(s);for(let c=0;c<=o;++c)i[c]=0;return[l,i]}i[0]=0;for(let l=1;l<=o;++l){const c=e[l]-e[l-1];let u=0;this.nGramWidths.forEach(h=>{u+=this.getNumNGrams(c,h)}),this.preserveShort&&c>0&&u===0&&(u=1),i[l]=i[l-1]+u}const a=new Array(i[o]);for(let l=0;l<o;++l){const c=e[l];let u=i[l];if(this.nGramWidths.forEach(h=>{const d=e[l+1]-e[l],f=this.getNumNGrams(d,h);this.createNGrams(t,c,a,u,f,h),u+=f}),this.preserveShort&&u===i[l]){const h=e[l+1]-e[l];if(h===0)continue;const d=h+2*this.padWidth;this.createNGrams(t,c,a,u,1,d)}}return[a,i]}}function U2(n,t,e,s,r,o,i,a){return new G2(e,s,r,o,i,a).compute(n,t)}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function H2(n,t,e,s){if(!n.length)return;if(t.length===0){for(let o=0;o<n.length;++o)s.push(n.subarray(o,o+1));return}if(t.length===1){const o=t[0];let i=n.indexOf(o);for(;i!==-1;){const a=n.subarray(0,i);(!e||a.length!==0)&&s.push(a),n=n.subarray(i+1),i=n.indexOf(o)}(!e||n.length!==0)&&s.push(n);return}let r=0;for(let o=0;o<n.length+1;o++)if(o===n.length||t.indexOf(n[o])!==-1){const i=n.subarray(r,o);(!e||i.length!==0)&&s.push(i),r=o+1}}function q2(n,t,e){const s=n.length,r=[];let o=0,i=0;const a=new Array(s);for(let d=0;d<s;++d){const f=r.length;H2(n[d],t,e,r);const p=r.length-f;a[d]=p,o+=p,i=Math.max(i,p)}const l=Gt("int32",o*2),c=new Array(o),u=[s,i];let h=0;for(let d=0;d<s;++d)for(let f=0;f<a[d];++f)l[h*2]=d,l[h*2+1]=f,c[h]=r[h],++h;return[l,c,u]}/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function j2(n,t){const e=Gt("int32",n.length);for(let s=0;s<n.length;++s)e[s]=Tg(n[s]).modulo(t).getLowBitsUnsigned();return e}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const K2=Vt(((n,t)=>n-t)),X2=cc(((n,t,e,s)=>({real:n-e,imag:t-s}))),uc=Xt(so,K2,X2),Z2={kernelName:so,backendName:"cpu",kernelFunc:uc};/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function J2(n,t){const e=new Array(n.rank);for(let r=0;r<e.length;r++)e[r]=n.shape[r]*t[r];const s=mt(e,n.dtype);for(let r=0;r<s.values.length;++r){const o=s.indexToLoc(r),i=new Array(n.rank);for(let l=0;l<i.length;l++)i[l]=o[l]%n.shape[l];const a=n.locToIndex(i);s.values[r]=n.values[a]}return s}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Ir=(n,t)=>{const e=t.value-n.value;return e===0?n.index-t.index:e};function sm(n,t,e=0,s=n.length-1){for(;s>e;){if(s-e>600){const a=s-e+1,l=t-e+1,c=Math.log(a),u=.5*Math.exp(2*c/3),h=.5*Math.sqrt(c*u*(a-u)/a)*Math.sign(l-a/2),d=Math.max(e,Math.floor(t-l*u/a+h)),f=Math.min(s,Math.floor(t+(a-l)*u/a+h));sm(n,t,d,f)}const r=n[t];let o=e,i=s;for(ds(n,e,t),Ir(n[s],r)>0&&ds(n,e,s);o<i;){for(ds(n,o,i),o++,i--;Ir(n[o],r)<0;)o=o+1;for(;Ir(n[i],r)>0;)i=i-1}Ir(n[e],r)===0?ds(n,e,i):(i=i+1,ds(n,i,s)),i<=t&&(e=i+1),t<=i&&(s=i-1)}}function Y2(n,t,e,s,r){const o=t[t.length-1],[i,a]=[n.length/o,o],l=he(e,i*s),c=he("int32",i*s);for(let h=0;h<i;h++){const d=h*a,f=n.subarray(d,d+a);let p=new Array(f.length);f.forEach((y,k)=>p[k]={value:y,index:k}),s<p.length&&(sm(p,s),p=p.slice(0,s)),r&&p.sort(Ir);const g=h*s,m=l.subarray(g,g+s),b=c.subarray(g,g+s);for(let y=0;y<s;y++)m[y]=p[y].value,b[y]=p[y].index}const u=t.slice();return u[u.length-1]=s,[mt(u,e,l),mt(u,"int32",c)]}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Q2(n,t,e,s){const r=Ft(t,e)[0],o=[1,e[0],1];for(let p=0;p<r;p++)o[0]*=e[p];o[1]=e[r];for(let p=r+1;p<e.length;p++)o[2]*=e[p];const i=new Map,a=new Int32Array(e[r]),l=new te(o,s,n),c=[],u=o[0]===1&&o[2]===1;for(let p=0;p<e[r];p++){let g;if(u)g=n[p].toString();else{const b=[];for(let y=0;y<o[0];y++)for(let k=0;k<o[2];k++)b.push(l.get(y,p,k));g=b.join(",")}const m=i.get(g);if(m!=null)a[p]=m;else{const b=i.size;i.set(g,b),a[p]=b,c.push(p)}}const h=o.slice();h[1]=i.size;const d=new te(h,s);c.forEach((p,g)=>{for(let m=0;m<o[0];m++)for(let b=0;b<o[2];b++)d.set(l.get(m,p,b),m,g,b)});const f=e.slice();return f[r]=h[1],{outputValues:d.values,outputShape:f,indices:a}}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */Kg("cpu",()=>new li,1);/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const rm=It(Rr,n=>n>=0?n:Math.exp(n)-1),t$={kernelName:Rr,backendName:"cpu",kernelFunc:rm};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function om(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{alpha:o}=s;et([r],"leakyRelu");const i=Z(r.shape),a=e.data.get(r.dataId).values,l=he("float32",i);for(let c=0;c<a.length;c++)l[c]=a[c]<0?o*a[c]:a[c];return e.makeTensorInfo(r.shape,"float32",l)}const e$={kernelName:sa,backendName:"cpu",kernelFunc:om};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const n$=Vt((n,t)=>n<0?t*n:n);function im(n){const{inputs:t,backend:e}=n,{x:s,alpha:r}=t;et([s,r],"prelu");const o=e.data.get(s.dataId).values,i=e.data.get(r.dataId).values,[a,l]=n$(s.shape,r.shape,o,i,"float32");return e.makeTensorInfo(l,"float32",a)}const s$={kernelName:ka,backendName:"cpu",kernelFunc:im};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const am=It(jr,n=>Math.max(0,n)),r$={kernelName:jr,backendName:"cpu",kernelFunc:am};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const lm=It(Kr,n=>Math.min(Math.max(0,n),6)),o$={kernelName:Kr,backendName:"cpu",kernelFunc:lm};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function di(n,t,e,s,r){if(e==="linear")return hn({inputs:{x:t},backend:n});if(e==="relu")return am({inputs:{x:t},backend:n});if(e==="elu")return rm({inputs:{x:t},backend:n});if(e==="relu6")return lm({inputs:{x:t},backend:n});if(e==="prelu")return im({inputs:{x:t,alpha:s},backend:n});if(e==="leakyrelu")return om({inputs:{x:t},backend:n,attrs:{alpha:r}});if(e==="sigmoid")return em({inputs:{x:t},backend:n});throw new Error(`Activation ${e} has not been implemented for the CPU backend.`)}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function At(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{shape:o}=s,i=Z(r.shape),a=Tm(o,i),l=Z(a);v(i===l,()=>`The new shape (${a}) has ${l} elements and the old shape (${r.shape}) has ${i} elements. The new shape and old shape must have the same number of elements.`),e.incRef(r.dataId);const c=e.data.get(r.dataId);if(c.complexTensorInfos!=null){const u=c.complexTensorInfos.real,h=c.complexTensorInfos.imag;u.shape=a,h.shape=a}return{dataId:r.dataId,shape:a,dtype:r.dtype}}const i$={kernelName:Ia,backendName:"cpu",kernelFunc:At};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function cm(n){const{inputs:t,backend:e,attrs:s}=n,{a:r,b:o}=t,{transposeA:i,transposeB:a}=s;et([r,o],"matMul");const l=r.shape.length,c=o.shape.length,u=i?r.shape[l-2]:r.shape[l-1],h=a?o.shape[c-1]:o.shape[c-2],d=i?r.shape[l-1]:r.shape[l-2],f=a?o.shape[c-2]:o.shape[c-1],p=r.shape.slice(0,-2),g=o.shape.slice(0,-2),m=Z(p),b=Z(g),k=Ct(r.shape.slice(0,-2),o.shape.slice(0,-2)).concat([d,f]);v(u===h,()=>`Error in matMul: inner shapes (${u}) and (${h}) of Tensors with shapes ${r.shape} and ${o.shape} and transposeA=${i} and transposeB=${a} must match.`);const w=i?[m,u,d]:[m,d,u],I=a?[b,f,h]:[b,h,f],S=At({inputs:{x:r},backend:e,attrs:{shape:w}}),T=At({inputs:{x:o},backend:e,attrs:{shape:I}}),C=i?S.shape[1]:S.shape[2],N=i?S.shape[2]:S.shape[1],$=a?T.shape[1]:T.shape[2],x=Math.max(m,b),F=e.data.get(S.dataId).values,M=e.data.get(T.dataId).values,O=it(S.shape),L=it(T.shape),[B,G,W]=i?[O[0],1,O[1]]:[O[0],O[1],1],[V,U,q]=a?[1,L[1],L[0]]:[L[1],1,L[0]],K=N*$,j=mt([x,N,$],S.dtype),Y=j.values,J=e.blockSize;for(let tt=0;tt<x;tt++){const nt=tt%m,at=tt%b;for(let ot=0;ot<N;ot+=J){const ht=Math.min(ot+J,N);for(let ft=0;ft<$;ft+=J){const St=Math.min(ft+J,$);for(let Et=0;Et<C;Et+=J){const Pt=Math.min(Et+J,C);for(let Dt=ot;Dt<ht;Dt++)for(let vt=ft;vt<St;vt++){let _t=0;for(let Lt=Et;Lt<Pt;Lt++){const kn=F[nt*B+Dt*G+Lt*W],re=M[Lt*V+vt*U+at*q];_t+=kn*re}Y[tt*K+(Dt*$+vt)]+=_t}}}}}return e.disposeIntermediateTensorInfo(S),e.disposeIntermediateTensorInfo(T),e.makeTensorInfo(k,j.dtype,j.values)}const a$={kernelName:Li,backendName:"cpu",kernelFunc:cm};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function l$(n){const{inputs:t,backend:e,attrs:s}=n,{a:r,b:o,bias:i,preluActivationWeights:a}=t,{transposeA:l,transposeB:c,activation:u,leakyreluAlpha:h}=s;let d,f,p;const g=[];d=cm({inputs:{a:r,b:o},attrs:{transposeA:l,transposeB:c},backend:e}),i&&(f=Os({inputs:{a:d,b:i},backend:e}),g.push(d),d=f),u&&(p=di(e,d,u,a,h),g.push(d),d=p);for(const b of g)e.disposeIntermediateTensorInfo(b);return d}const c$={kernelName:_a,backendName:"cpu",kernelFunc:l$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const u$=It($i,n=>Math.acos(n)),h$={kernelName:$i,backendName:"cpu",kernelFunc:u$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const d$=It(Ti,n=>Math.acosh(n)),f$={kernelName:Ti,backendName:"cpu",kernelFunc:d$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function p$(n){const{inputs:t,backend:e}=n,s=t;et(t,"addN");const r=s.map(a=>e.data.get(a.dataId).values),o=mt(s[0].shape,s[0].dtype),i=o.values;for(let a=0;a<s.length;a++){const l=r[a];for(let c=0;c<i.length;c++)i[c]+=l[c]}return e.makeTensorInfo(o.shape,o.dtype,o.values)}const m$={kernelName:Tc,backendName:"cpu",kernelFunc:p$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function g$(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{axis:o,keepDims:i}=s;et(r,"all");const a=Ft(o,r.shape);let l=a;const c=Ce(l,r.shape.length);let u=r;c!=null&&(u=me({inputs:{x:r},backend:e,attrs:{perm:c}}),l=Ye(l.length,r.shape.length)),ts("all",l,u.shape.length);const[h,d]=Je(u.shape,l),f=Z(d),p=ie(Z(h),u.dtype),g=e.data.get(u.dataId).values;for(let b=0;b<p.length;++b){const y=b*f;let k=g[y];for(let w=0;w<f;++w){const I=g[y+w];k=k&&I}p[b]=k}c!=null&&e.disposeIntermediateTensorInfo(u);const m=e.makeTensorInfo(h,u.dtype,p);if(i){const b=Te(h,a),y=At({inputs:{x:m},backend:e,attrs:{shape:b}});return e.disposeIntermediateTensorInfo(m),y}return m}const b$={kernelName:Cc,backendName:"cpu",kernelFunc:g$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function y$(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{axis:o,keepDims:i}=s;et(r,"any");const a=Ft(o,r.shape);let l=a;const c=Ce(l,r.shape.length);let u=r;c!=null&&(u=me({inputs:{x:r},backend:e,attrs:{perm:c}}),l=Ye(l.length,r.shape.length)),ts("any",l,u.shape.length);const[h,d]=Je(u.shape,l),f=Z(d),p=ie(Z(h),u.dtype),g=e.data.get(u.dataId).values;for(let b=0;b<p.length;++b){const y=b*f;let k=g[y];for(let w=0;w<f;++w){const I=g[y+w];k=k||I}p[b]=k}c!=null&&e.disposeIntermediateTensorInfo(u);const m=e.makeTensorInfo(h,u.dtype,p);if(i){const b=Te(h,a),y=At({inputs:{x:m},backend:e,attrs:{shape:b}});return e.disposeIntermediateTensorInfo(m),y}return m}const w$={kernelName:Ac,backendName:"cpu",kernelFunc:y$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function k$(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{axis:o}=s;et(r,"argMax");let i=Ft(o,r.shape);const a=Ce(i,r.shape.length);let l=r;const c=[];a!=null&&(l=me({inputs:{x:r},backend:e,attrs:{perm:a}}),c.push(l),i=Ye(i.length,l.shape.length)),i=[i[0]],ts("argMax",i,l.shape.length);const[u,h]=Je(l.shape,i),d=Z(u),f=ie(d,"int32"),p=Z(h),g=e.data.get(l.dataId).values;for(let m=0;m<f.length;++m){const b=m*p;let y=g[b],k=0;for(let w=0;w<p;++w){const I=g[b+w];I>y&&(y=I,k=w)}f[m]=k}return c.forEach(m=>e.disposeIntermediateTensorInfo(m)),e.makeTensorInfo(u,"int32",f)}const x$={kernelName:Ci,backendName:"cpu",kernelFunc:k$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function I$(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{axis:o}=s;et(r,"argMin");let i=Ft(o,r.shape);const a=Ce(i,r.shape.length);let l=r;const c=[];a!=null&&(l=me({inputs:{x:r},backend:e,attrs:{perm:a}}),c.push(l),i=Ye(i.length,l.shape.length)),i=[i[0]],ts("argMin",i,l.shape.length);const[u,h]=Je(l.shape,i),d=Z(u),f=ie(d,"int32"),p=Z(h),g=e.data.get(l.dataId).values;for(let m=0;m<f.length;++m){const b=m*p;let y=g[b],k=0;for(let w=0;w<p;++w){const I=g[b+w];I<y&&(y=I,k=w)}f[m]=k}return c.forEach(m=>e.disposeIntermediateTensorInfo(m)),e.makeTensorInfo(u,"int32",f)}const S$={kernelName:Ec,backendName:"cpu",kernelFunc:I$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const v$=It(Ai,n=>Math.asin(n)),N$={kernelName:Ai,backendName:"cpu",kernelFunc:v$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const $$=It(Ei,n=>Math.asinh(n)),T$={kernelName:Ei,backendName:"cpu",kernelFunc:$$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const C$=It(Di,n=>Math.atan(n)),A$={kernelName:Di,backendName:"cpu",kernelFunc:C$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const E$=Vt((n,t)=>Math.atan2(n,t)),D$=Xt(Mi,E$),F$={kernelName:Mi,backendName:"cpu",kernelFunc:D$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const M$=It(Fi,n=>Math.atanh(n)),R$={kernelName:Fi,backendName:"cpu",kernelFunc:M$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function hc(n,t,e,s,r,o){const i=r.strideHeight,a=r.strideWidth,l=r.dilationHeight,c=r.dilationWidth,u=r.effectiveFilterHeight,h=r.effectiveFilterWidth,d=r.padInfo.top,f=r.padInfo.left,p=o==="max"?Number.NEGATIVE_INFINITY:Number.POSITIVE_INFINITY,g=mt(r.outShape,e),m=g.values,b=r.outShape[1]*r.outShape[2]*r.outShape[3],y=r.outShape[2]*r.outShape[3],k=r.outShape[3];for(let w=0;w<r.batchSize;++w){const I=w*b,S=w*s[0];for(let T=0;T<r.inChannels;++T)for(let C=0;C<r.outHeight;++C){const N=C*i-d,$=Math.max(0,N),x=Math.min(r.inHeight,u+N),F=I+C*y;for(let M=0;M<r.outWidth;++M){const O=M*a-f,L=Math.max(0,O),B=Math.min(r.inWidth,h+O);let G=p,W=0,V=0;for(let q=$;q<x;q+=l){const K=S+q*s[1];for(let j=L;j<B;j+=c){const Y=K+j*s[2],J=n[Y+T];o==="max"&&J>G?G=J:o==="avg"&&(W+=J,V++)}if(isNaN(G))break}const U=F+M*k+T;m[U]=o==="avg"?W/V:G}}}return g}function um(n,t,e,s,r=!1,o=!1){const i=mt(s.outShape,"int32"),a=s.strideHeight,l=s.strideWidth,c=s.dilationHeight,u=s.dilationWidth,h=s.effectiveFilterHeight,d=s.effectiveFilterWidth,f=s.padInfo.top,p=s.padInfo.left,g=mt(t,e,n);for(let m=0;m<s.batchSize;++m)for(let b=0;b<s.inChannels;++b)for(let y=0;y<s.outHeight;++y){const k=y*a-f;let w=k;for(;w<0;)w+=c;const I=Math.min(s.inHeight,h+k);for(let S=0;S<s.outWidth;++S){const T=S*l-p;let C=T;for(;C<0;)C+=u;const N=Math.min(s.inWidth,d+T);let $=Number.NEGATIVE_INFINITY,x=-1;for(let F=w;F<I;F+=c){const M=F-k;for(let O=C;O<N;O+=u){const L=O-T,B=g.get(m,F,O,b);B>$&&($=B,r?x=o?((m*s.inHeight+F)*s.inWidth+O)*s.inChannels+b:(F*s.inWidth+O)*s.inChannels+b:x=M*d+L)}}i.set(x,m,y,S,b)}}return i}function hm(n,t,e,s,r,o){const i=r.strideDepth,a=r.strideHeight,l=r.strideWidth,c=r.dilationDepth,u=r.dilationHeight,h=r.dilationWidth,d=r.effectiveFilterDepth,f=r.effectiveFilterHeight,p=r.effectiveFilterWidth,g=r.padInfo.front,m=r.padInfo.top,b=r.padInfo.left,y=o==="max"?Number.NEGATIVE_INFINITY:Number.POSITIVE_INFINITY,k=mt(r.outShape,e),w=k.values,I=r.outShape[1]*r.outShape[2]*r.outShape[3]*r.outShape[4],S=r.outShape[2]*r.outShape[3]*r.outShape[4],T=r.outShape[3]*r.outShape[4],C=r.outShape[4];for(let N=0;N<r.batchSize;++N){const $=N*I,x=N*s[0];for(let F=0;F<r.inChannels;++F)for(let M=0;M<r.outDepth;++M){const O=M*i-g;let L=O;for(;L<0;)L+=c;const B=Math.min(r.inDepth,d+O),G=$+M*S;for(let W=0;W<r.outHeight;++W){const V=W*a-m;let U=V;for(;U<0;)U+=u;const q=Math.min(r.inHeight,f+V),K=G+W*T;for(let j=0;j<r.outWidth;++j){const Y=j*l-b;let J=Y;for(;J<0;)J+=h;const tt=Math.min(r.inWidth,p+Y),nt=K+j*C;let at=y,ot=0,ht=0;for(let St=L;St<B;St+=c){const Et=x+St*s[1];for(let Pt=U;Pt<q;Pt+=u){const Dt=Et+Pt*s[2];for(let vt=J;vt<tt;vt+=h){const _t=Dt+vt*s[3],Lt=n[_t+F];if(o==="max"&&Lt>at?at=Lt:o==="avg"&&(ot+=Lt,ht++),isNaN(at))break}if(isNaN(at))break}if(isNaN(at))break}const ft=nt+F;w[ft]=o==="avg"?ot/Math.max(ht,1):at}}}}return k}function z$(n,t){const e=mt(t.outShape,"int32"),s=t.strideDepth,r=t.strideHeight,o=t.strideWidth,i=t.dilationDepth,a=t.dilationHeight,l=t.dilationWidth,c=t.effectiveFilterDepth,u=t.effectiveFilterHeight,h=t.effectiveFilterWidth,d=t.padInfo.front,f=t.padInfo.top,p=t.padInfo.left;for(let g=0;g<t.batchSize;++g)for(let m=0;m<t.inChannels;++m)for(let b=0;b<t.outDepth;++b){const y=b*s-d;let k=y;for(;k<0;)k+=i;const w=Math.min(t.inDepth,c+y);for(let I=0;I<t.outHeight;++I){const S=I*r-f;let T=S;for(;T<0;)T+=a;const C=Math.min(t.inHeight,u+S);for(let N=0;N<t.outWidth;++N){const $=N*o-p;let x=$;for(;x<0;)x+=l;const F=Math.min(t.inWidth,h+$);let M=Number.NEGATIVE_INFINITY,O=-1;for(let L=k;L<w;L+=i){const B=L-y;for(let G=T;G<C;G+=a){const W=G-S;for(let V=x;V<F;V+=l){const U=V-$,q=n.get(g,L,G,V,m);q>=M&&(M=q,O=B*u*h+W*u+U)}}}e.set(O,g,b,I,N,m)}}}return e}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function L$(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t;et(r,"avgPool");const{filterSize:o,strides:i,pad:a,dimRoundingMode:l}=s,c=1;v(Ze(i,c),()=>`Error in avgPool: Either strides or dilations must be 1. Got strides ${i} and dilations '${c}'`);const u=Zs(r.shape,o,i,c,a,l);let h;if(u.filterWidth===1&&u.filterHeight===1&&oe(u.inShape,u.outShape))h=hn({inputs:{x:r},backend:e});else{const d=e.data.get(r.dataId).values,f=it(r.shape),p=hc(d,r.shape,r.dtype,f,u,"avg");h=e.makeTensorInfo(u.outShape,r.dtype,p.values)}return h}const O$={kernelName:Ri,backendName:"cpu",kernelFunc:L$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function _$(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{filterSize:o,strides:i,pad:a,dimRoundingMode:l,dataFormat:c}=s;et(r,"avgPool3d");const u=yo(r.shape,o,i,1,a,l,c),h=e.data.get(r.dataId).values,d=hm(h,r.shape,r.dtype,it(r.shape),u,"avg");return e.makeTensorInfo(d.shape,"float32",d.values)}const B$={kernelName:zi,backendName:"cpu",kernelFunc:_$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function P$(n){const{inputs:t,backend:e,attrs:s}=n,{dy:r,input:o}=t,{filterSize:i,strides:a,pad:l,dimRoundingMode:c}=s;et([r,o],"avgPool3DGrad");const u=yo(o.shape,i,a,1,l,c),h=u.strideDepth,d=u.strideHeight,f=u.strideWidth,p=u.filterDepth,g=u.filterHeight,m=u.filterWidth,b=u.dilationDepth,y=u.dilationHeight,k=u.dilationWidth,w=u.effectiveFilterDepth,I=u.effectiveFilterHeight,S=u.effectiveFilterWidth,T=w-1-u.padInfo.front,C=S-1-u.padInfo.left,N=I-1-u.padInfo.top,$=mt(o.shape,"float32"),x=1/(p*g*m),F=e.bufferSync(r);for(let M=0;M<u.batchSize;++M)for(let O=0;O<u.inChannels;++O)for(let L=0;L<u.inDepth;++L)for(let B=0;B<u.inHeight;++B)for(let G=0;G<u.inWidth;++G){const W=L-T,V=B-N,U=G-C;let q=0;for(let K=0;K<w;K+=b){const j=(W+K)/h;if(!(j<0||j>=u.outDepth||Math.floor(j)!==j))for(let Y=0;Y<I;Y+=y){const J=(V+Y)/d;if(!(J<0||J>=u.outHeight||Math.floor(J)!==J))for(let tt=0;tt<S;tt+=k){const nt=(U+tt)/f;if(nt<0||nt>=u.outWidth||Math.floor(nt)!==nt)continue;const at=F.get(M,j,J,nt,O);q+=at}}}$.set(q*x,M,L,B,G,O)}return e.makeTensorInfo($.shape,$.dtype,$.values)}const W$={kernelName:Fc,backendName:"cpu",kernelFunc:P$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function V$(n){const{inputs:t,backend:e,attrs:s}=n,{dy:r,input:o}=t,i=o;et([r,o],"avgPoolGrad");const{filterSize:a,strides:l,pad:c}=s,u=Zs(i.shape,a,l,1,c),h=u.strideHeight,d=u.strideWidth,f=u.filterHeight,p=u.filterWidth,g=u.dilationHeight,m=u.dilationWidth,b=u.effectiveFilterHeight,y=u.effectiveFilterWidth,k=y-1-u.padInfo.left,w=b-1-u.padInfo.top,I=mt(i.shape,"float32"),S=1/(f*p),T=e.data.get(r.dataId).values,C=mt(r.shape,"float32",T);for(let N=0;N<u.batchSize;++N)for(let $=0;$<u.inChannels;++$)for(let x=0;x<u.inHeight;++x)for(let F=0;F<u.inWidth;++F){const M=x-w,O=F-k;let L=0;for(let B=0;B<b;B+=g){const G=(M+B)/h;if(!(G<0||G>=u.outHeight||Math.floor(G)!==G))for(let W=0;W<y;W+=m){const V=(O+W)/d;if(V<0||V>=u.outWidth||Math.floor(V)!==V)continue;const U=C.get(N,G,V,$);L+=U}}I.set(L*S,N,x,F,$)}return e.makeTensorInfo(I.shape,I.dtype,I.values)}const G$={kernelName:Dc,backendName:"cpu",kernelFunc:V$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function U$(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,scale:o,offset:i,mean:a,variance:l}=t;v(a.shape.length===l.shape.length,()=>"Batch normalization gradient requires mean and variance to have equal ranks."),v(i==null||a.shape.length===i.shape.length,()=>"Batch normalization gradient requires mean and offset to have equal ranks."),v(o==null||a.shape.length===o.shape.length,()=>"Batch normalization gradient requires mean and scale to have equal ranks."),et([r,a,l,o,i],"batchNorm");let{varianceEpsilon:c}=s;c==null&&(c=.001);const u=e.data.get(r.dataId).values,h=e.data.get(a.dataId).values,d=e.data.get(l.dataId).values,f=o?e.data.get(o.dataId).values:new Float32Array([1]),p=i?e.data.get(i.dataId).values:new Float32Array([0]),g=new Float32Array(u.length),m=p.length,b=f.length,y=d.length,k=h.length;let w=0,I=0,S=0,T=0;for(let C=0;C<u.length;++C)g[C]=p[w++]+(u[C]-h[I++])*f[S++]/Math.sqrt(d[T++]+c),w>=m&&(w=0),I>=k&&(I=0),S>=b&&(S=0),T>=y&&(T=0);return e.makeTensorInfo(r.shape,r.dtype,g)}const H$={kernelName:Ji,backendName:"cpu",kernelFunc:U$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function q$(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{blockShape:o,crops:i}=s;et([r],"batchToSpaceND");const a=o.reduce((b,y)=>b*y),l=Hh(r.shape,o,a),c=qh(l.length,o.length),u=jh(r.shape,o,a),h=kk(i,o.length),d=xk(u,i,o.length),f=At({inputs:{x:r},backend:e,attrs:{shape:l}}),p=me({inputs:{x:f},backend:e,attrs:{perm:c}}),g=At({inputs:{x:p},backend:e,attrs:{shape:u}}),m=us({inputs:{x:g},backend:e,attrs:{begin:h,size:d}});return e.disposeIntermediateTensorInfo(f),e.disposeIntermediateTensorInfo(p),e.disposeIntermediateTensorInfo(g),m}const j$={kernelName:Oi,backendName:"cpu",kernelFunc:q$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function K$(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,weights:o}=t,{size:i}=s,a=e.data.get(r.dataId).values,l=e.data.get(o.dataId).values,c=qp(a,l,o.dtype,o.shape,i);return e.makeTensorInfo([i],o.dtype,c)}const X$={kernelName:Mc,backendName:"cpu",kernelFunc:K$};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Z$(n){const{inputs:t,backend:e}=n,{s0:s,s1:r}=t,o=e.data.get(s.dataId).values,i=e.data.get(r.dataId).values,a=Ct(Array.from(o),Array.from(i));return e.makeTensorInfo([a.length],"int32",Int32Array.from(a))}const J$={kernelName:Vm,backendName:"cpu",kernelFunc:Z$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const Y$=It(Er,(n,t)=>{const e=t;return n>e.clipValueMax?e.clipValueMax:n<e.clipValueMin?e.clipValueMin:n}),Q$={kernelName:Er,backendName:"cpu",kernelFunc:Y$};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const tT={kernelName:Bi,backendName:"cpu",kernelFunc:n=>{const{x:t}=n.inputs,e=n.backend,s=new Float32Array(Z(t.shape)),r=e.data.get(t.dataId),o=r.complexTensorInfos.real,i=r.complexTensorInfos.imag,a=e.data.get(o.dataId).values,l=e.data.get(i.dataId).values;for(let c=0;c<a.length;c++){const u=a[c],h=l[c];s[c]=Math.hypot(u,h)}return e.makeOutput(s,t.shape,"float32")}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Bs(n){const{inputs:t,backend:e}=n,{input:s}=t,r=e.data.get(s.dataId).complexTensorInfos.imag,o=e.data.get(r.dataId).values;return e.makeTensorInfo(r.shape,r.dtype,o)}const eT={kernelName:Xc,backendName:"cpu",kernelFunc:Bs};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Ps(n){const{inputs:t,backend:e,attrs:s}=n,{axis:r}=s,o=Ft(r,t[0].shape)[0],i=t.map(g=>g.shape);pk(i,o);let a=vl(t.map(g=>g.shape),o);if(Z(a)===0)return e.makeTensorInfo(a,t[0].dtype,[]);const l=t.filter(g=>Z(g.shape)>0);if(l.length===1)return hn({inputs:{x:l[0]},backend:e});if(l[0].dtype==="complex64"){const g=l.map(w=>cs({inputs:{input:w},backend:e})),m=l.map(w=>Bs({inputs:{input:w},backend:e})),b=Ps({inputs:g,backend:e,attrs:{axis:o}}),y=Ps({inputs:m,backend:e,attrs:{axis:o}}),k=Ie({inputs:{real:b,imag:y},backend:e});return g.forEach(w=>e.disposeIntermediateTensorInfo(w)),m.forEach(w=>e.disposeIntermediateTensorInfo(w)),e.disposeIntermediateTensorInfo(b),e.disposeIntermediateTensorInfo(y),k}const c=l.map(g=>{const b=[-1,Z(g.shape.slice(o))];return At({inputs:{x:g},backend:e,attrs:{shape:b}})}),u=c.map(g=>({vals:e.data.get(g.dataId).values,shape:g.shape}));a=vl(c.map(g=>g.shape),1);const h=c[0].shape[0]===1,d=wN(u,a,t[0].dtype,h),f=vl(l.map(g=>g.shape),o),p=e.makeTensorInfo(f,t[0].dtype,d);return c.forEach(g=>e.disposeIntermediateTensorInfo(g)),p}const nT={kernelName:Pi,backendName:"cpu",kernelFunc:Ps};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function dm(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,filter:o}=t,{strides:i,pad:a,dataFormat:l,dilations:c,dimRoundingMode:u}=s;et([r,o],"conv2d");const h=ko(l),d=pn(r.shape,o.shape,i,c,a,u,!1,h),f=d.filterHeight,p=d.filterWidth,g=d.dilationHeight,m=d.dilationWidth,b=d.padInfo.left,y=d.padInfo.top,k=d.dataFormat==="channelsLast",w=new te(d.outShape,r.dtype),I=it(r.shape),S=it(o.shape),T=I[0],C=k?I[1]:I[2],N=k?I[2]:1,$=k?1:I[1],x=w.strides[0],F=k?w.strides[1]:w.strides[2],M=k?w.strides[2]:1,O=k?1:w.strides[1],L=e.data.get(r.dataId).values,B=e.data.get(o.dataId).values,G=w.values;for(let W=0;W<d.batchSize;++W){const V=W*T,U=W*x;for(let q=0;q<d.outHeight;++q){const K=U+q*F,j=q*d.strideHeight-y;for(let Y=0;Y<f;++Y){const J=j+Y*g;if(J<0||J>=d.inHeight)continue;const tt=Y*S[0],nt=V+J*C;for(let at=0;at<d.outWidth;++at){const ot=K+at*M,ht=at*d.strideWidth-b;for(let ft=0;ft<p;++ft){const St=ht+ft*m;if(St<0||St>=d.inWidth)continue;const Et=tt+ft*S[1],Pt=nt+St*N;let Dt=Et;for(let vt=0;vt<d.inChannels;++vt){const _t=L[Pt+vt*$];for(let Lt=0;Lt<d.outChannels;++Lt)G[ot+Lt*O]+=_t*B[Dt+Lt];Dt+=d.outChannels}}}}}}return e.makeTensorInfo(w.shape,w.dtype,G)}const sT={kernelName:Wi,backendName:"cpu",kernelFunc:dm};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function rT(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,dy:o}=t,{strides:i,pad:a,dataFormat:l,dimRoundingMode:c,filterShape:u}=s;et([r,o],"conv2dBackpropFilter");const h=ko(l),d=pn(r.shape,u,i,1,a,c,!1,h),{strideHeight:f,strideWidth:p,filterHeight:g,filterWidth:m}=d,b=d.dataFormat==="channelsLast",y=new te(d.filterShape,"float32"),k=d.padInfo.left,w=d.padInfo.top,I=e.data.get(r.dataId).values,S=e.data.get(o.dataId).values,T=new te(r.shape,r.dtype,I),C=new te(o.shape,o.dtype,S);for(let N=0;N<g;++N){const $=Math.max(0,Math.ceil((w-N)/f)),x=Math.min(d.outHeight,(d.inHeight+w-N)/f);for(let F=0;F<m;++F){const M=Math.max(0,Math.ceil((k-F)/p)),O=Math.min(d.outWidth,(d.inWidth+k-F)/p);for(let L=0;L<d.inChannels;++L)for(let B=0;B<d.outChannels;++B){let G=0;for(let W=0;W<d.batchSize;++W)for(let V=$;V<x;++V){const U=N+V*f-w;for(let q=M;q<O;++q){const K=F+q*p-k;b?G+=T.get(W,U,K,L)*C.get(W,V,q,B):G+=T.get(W,L,U,K)*C.get(W,B,V,q)}}y.set(G,N,F,L,B)}}}return e.makeTensorInfo(y.shape,y.dtype,y.values)}const oT={kernelName:Lc,backendName:"cpu",kernelFunc:rT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function iT(n){const{inputs:t,backend:e,attrs:s}=n,{dy:r,filter:o}=t,{inputShape:i,strides:a,pad:l,dataFormat:c,dimRoundingMode:u}=s;et([r,o],"conv2dBackpropInput");const h=it(o.shape),d=it(r.shape);let f=ko(c);const p=pn(i,o.shape,a,1,l,u,!1,f),g=new te(p.inShape,"float32"),m=g.values,b=e.data.get(r.dataId).values,y=e.data.get(o.dataId).values,[k,w,I]=h,{batchSize:S,filterHeight:T,filterWidth:C,inChannels:N,inHeight:$,inWidth:x,outChannels:F,outHeight:M,outWidth:O,strideHeight:L,strideWidth:B}=p;f=p.dataFormat;const G=T-1-p.padInfo.top,W=C-1-p.padInfo.left,V=f==="channelsLast",U=g.strides[0],q=V?g.strides[1]:g.strides[2],K=V?g.strides[2]:1,j=V?1:g.strides[1],Y=d[0],J=V?d[1]:d[2],tt=V?d[2]:1,nt=V?1:d[1];for(let at=0;at<S;++at)for(let ot=0;ot<N;++ot)for(let ht=0;ht<$;++ht){const ft=ht-G,St=Math.max(0,Math.ceil(ft/L)),Et=Math.min(M,(T+ft)/L);for(let Pt=0;Pt<x;++Pt){const Dt=Pt-W,vt=Math.max(0,Math.ceil(Dt/B)),_t=Math.min(O,(C+Dt)/B);let Lt=0;for(let re=St;re<Et;++re){const Vn=re*L-ft;for(let ve=vt;ve<_t;++ve){const hs=ve*B-Dt,qe=Y*at+J*re+tt*ve,xn=k*(T-1-Vn)+w*(C-1-hs)+I*ot;for(let Gn=0;Gn<F;++Gn){const Un=b[qe+nt*Gn],Hn=y[xn+Gn];Lt+=Un*Hn}}}const kn=U*at+q*ht+K*Pt+j*ot;m[kn]=Lt}}return e.makeTensorInfo(g.shape,g.dtype,g.values)}const aT={kernelName:Vi,backendName:"cpu",kernelFunc:iT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function lT(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,filter:o}=t,{strides:i,pad:a,dilations:l}=s;et([r,o],"conv3d");const c=wo(r.shape,o.shape,i,l,a),{filterDepth:u,filterHeight:h,filterWidth:d,dilationDepth:f,dilationHeight:p,dilationWidth:g,padInfo:m}=c,b=m.front,y=m.left,k=m.top,w=new te(c.outShape,r.dtype),I=e.data.get(r.dataId).values,S=e.data.get(o.dataId).values,T=w.values,C=it(r.shape),N=it(o.shape);for(let $=0;$<c.batchSize;++$){const x=$*C[0],F=$*w.strides[0];for(let M=0;M<c.outDepth;++M){const O=F+M*w.strides[1],L=M*c.strideDepth-b;for(let B=0;B<u;++B){const G=L+B*f;if(G<0||G>=c.inDepth)continue;const W=B*N[0],V=x+G*C[1];for(let U=0;U<c.outHeight;++U){const q=O+U*w.strides[2],K=U*c.strideHeight-k;for(let j=0;j<h;++j){const Y=K+j*p;if(Y<0||Y>=c.inHeight)continue;const J=W+j*N[1],tt=V+Y*C[2];for(let nt=0;nt<c.outWidth;++nt){const at=q+nt*c.outChannels,ot=nt*c.strideWidth-y;for(let ht=0;ht<d;++ht){const ft=ot+ht*g;if(ft<0||ft>=c.inWidth)continue;const St=J+ht*N[2],Et=tt+ft*c.inChannels;let Pt=St;for(let Dt=0;Dt<c.inChannels;++Dt){const vt=I[Et+Dt];for(let _t=0;_t<c.outChannels;++_t)T[at+_t]+=vt*S[Pt+_t];Pt+=c.outChannels}}}}}}}}return e.makeTensorInfo(w.shape,w.dtype,w.values)}const cT={kernelName:Gi,backendName:"cpu",kernelFunc:lT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function uT(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,dy:o}=t,{strides:i,pad:a,filterShape:l}=s;et([r,o],"conv3dBackpropFilterV2");const c=it(r.shape),u=it(o.shape),h=wo(r.shape,l,i,1,a),d=h.strideDepth,f=h.strideHeight,p=h.strideWidth,g=h.filterDepth,m=h.filterHeight,b=h.filterWidth,y=new te(h.filterShape,"float32"),k=y.values,[w,I,S,T]=y.strides,C=e.data.get(o.dataId).values,[N,$,x,F]=u,M=e.data.get(r.dataId).values,[O,L,B,G]=c,W=h.padInfo.front,V=h.padInfo.left,U=h.padInfo.top;for(let q=0;q<g;++q){const K=Math.max(0,Math.ceil((W-q)/d)),j=Math.min(h.outDepth,(h.inDepth+W-q)/d),Y=q*w;for(let J=0;J<m;++J){const tt=Math.max(0,Math.ceil((U-J)/f)),nt=Math.min(h.outHeight,(h.inHeight+U-J)/f),at=J*I+Y;for(let ot=0;ot<b;++ot){const ht=Math.max(0,Math.ceil((V-ot)/p)),ft=Math.min(h.outWidth,(h.inWidth+V-ot)/p),St=ot*S+at;for(let Et=0;Et<h.inChannels;++Et){const Pt=Et*T+St;for(let Dt=0;Dt<h.outChannels;++Dt){let vt=0;for(let _t=0;_t<h.batchSize;++_t){const Lt=_t*O,kn=_t*N;for(let re=K;re<j;++re){const ve=(q+re*d-W)*L+Lt,hs=re*$+kn;for(let qe=tt;qe<nt;++qe){const Gn=(J+qe*f-U)*B+ve,Un=qe*x+hs;for(let Hn=ht;Hn<ft;++Hn){const bc=(ot+Hn*p-V)*G+Gn,yc=Hn*F+Un;vt+=M[bc+Et]*C[yc+Dt]}}}}k[Pt+Dt]=vt}}}}}return e.makeTensorInfo(y.shape,y.dtype,y.values)}const hT={kernelName:Oc,backendName:"cpu",kernelFunc:uT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function dT(n){const{inputs:t,backend:e,attrs:s}=n,{dy:r,filter:o}=t,{pad:i,strides:a,inputShape:l}=s;et([r],"conv3dBackpropInputV2");const c=it(r.shape),u=it(o.shape),h=wo(l,o.shape,a,1,i),d=new te(h.inShape,"float32"),f=d.values,[p,g,m,b]=d.strides,y=e.data.get(r.dataId).values,[k,w,I,S]=c,T=e.data.get(o.dataId).values,[C,N,$,x]=u,{batchSize:F,filterDepth:M,filterHeight:O,filterWidth:L,inChannels:B,inDepth:G,inHeight:W,inWidth:V,outChannels:U,outDepth:q,outHeight:K,outWidth:j,strideDepth:Y,strideHeight:J,strideWidth:tt}=h,nt=M-1-h.padInfo.front,at=O-1-h.padInfo.top,ot=L-1-h.padInfo.left;for(let ht=0;ht<F;++ht)for(let ft=0;ft<B;++ft)for(let St=0;St<G;++St){const Et=St-nt,Pt=Math.max(0,Math.ceil(Et/Y)),Dt=Math.min(q,(M+Et)/Y);for(let vt=0;vt<W;++vt){const _t=vt-at,Lt=Math.max(0,Math.ceil(_t/J)),kn=Math.min(K,(O+_t)/J);for(let re=0;re<V;++re){const Vn=re-ot,ve=Math.max(0,Math.ceil(Vn/tt)),hs=Math.min(j,(L+Vn)/tt);let qe=0;for(let xn=Pt;xn<Dt;++xn){const Gn=xn*Y-Et;for(let Un=Lt;Un<kn;++Un){const Hn=Un*J-_t;for(let Nr=ve;Nr<hs;++Nr){const bc=Nr*tt-Vn,yc=k*ht+w*xn+I*Un+S*Nr,gD=C*(M-1-Gn)+N*(O-1-Hn)+$*(L-1-bc)+x*ft;for(let gi=0;gi<U;++gi){const bD=y[yc+gi],yD=T[gD+gi];qe+=bD*yD}}}}f[p*ht+g*St+m*vt+b*re+ft]=qe}}}return e.makeTensorInfo(d.shape,d.dtype,d.values)}const fT={kernelName:_c,backendName:"cpu",kernelFunc:dT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const pT=It(Dr,n=>Math.cos(n)),mT={kernelName:Dr,backendName:"cpu",kernelFunc:pT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const gT=It(Fr,n=>Math.cosh(n)),bT={kernelName:Fr,backendName:"cpu",kernelFunc:gT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function yT(n){const{inputs:t,backend:e,attrs:s}=n,{image:r,boxes:o,boxInd:i}=t,{cropSize:a,method:l,extrapolationValue:c}=s,[u,h,d,f]=r.shape,p=o.shape[0],[g,m]=a,b=mt([p,g,m,f],"float32"),y=e.data.get(o.dataId).values,k=e.data.get(i.dataId).values,w=e.data.get(r.dataId).values,I=it(r.shape),S=it(b.shape);for(let T=0;T<p;T++){const C=T*4,N=y[C],$=y[C+1],x=y[C+2],F=y[C+3],M=k[T];if(M>=u)continue;const O=g>1?(x-N)*(h-1)/(g-1):0,L=m>1?(F-$)*(d-1)/(m-1):0;for(let B=0;B<g;B++){const G=g>1?N*(h-1)+B*O:.5*(N+x)*(h-1);if(G<0||G>h-1){for(let W=0;W<m;W++)for(let V=0;V<f;V++){const U=V+W*S[2]+B*S[1]+T*S[0];b.values[U]=c}continue}if(l==="bilinear"){const W=Math.floor(G),V=Math.ceil(G),U=G-W;for(let q=0;q<m;q++){const K=m>1?$*(d-1)+q*L:.5*($+F)*(d-1);if(K<0||K>d-1){for(let tt=0;tt<f;tt++){const nt=tt+q*S[2]+B*S[1]+T*S[0];b.values[nt]=c}continue}const j=Math.floor(K),Y=Math.ceil(K),J=K-j;for(let tt=0;tt<f;tt++){let nt=tt+j*I[2]+W*I[1]+M*I[0];const at=w[nt];nt=tt+Y*I[2]+W*I[1]+M*I[0];const ot=w[nt];nt=tt+j*I[2]+V*I[1]+M*I[0];const ht=w[nt];nt=tt+Y*I[2]+V*I[1]+M*I[0];const ft=w[nt],St=at+(ot-at)*J,Et=ht+(ft-ht)*J;nt=tt+q*S[2]+B*S[1]+T*S[0],b.values[nt]=St+(Et-St)*U}}}else for(let W=0;W<m;++W){const V=m>1?$*(d-1)+W*L:.5*($+F)*(d-1);if(V<0||V>d-1){for(let K=0;K<f;K++){const j=K+W*S[2]+B*S[1]+T*S[0];b.values[j]=c}continue}const U=Math.round(V),q=Math.round(G);for(let K=0;K<f;K++){const j=K+U*I[2]+q*I[1]+M*I[0],Y=K+W*S[2]+B*S[1]+T*S[0];b.values[Y]=w[j]}}}}return e.makeTensorInfo(b.shape,b.dtype,b.values)}const wT={kernelName:Pc,backendName:"cpu",kernelFunc:yT};/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function kT(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{axis:o,exclusive:i,reverse:a}=s;et(r,"cumprod");const l=Ce([o],r.shape.length);let c=r;l!=null&&(c=me({inputs:{x:r},backend:e,attrs:{perm:l}}));const u=Ye(1,r.shape.length)[0];if(u!==c.shape.length-1)throw new Error(`backend.cumprod in CPU expects an inner-most axis=${c.shape.length-1} but got axis=${u}`);const h=ms(c.dtype,"int32"),d=xi(Z(c.shape),h),f=e.data.get(c.dataId).values,p=c.shape[c.shape.length-1],g=a?(b,y)=>b+p-y-1:(b,y)=>b+y;for(let b=0;b<f.length;b+=p)for(let y=0;y<p;y++){const k=g(b,y);if(y===0)d[k]=i?1:f[k];else{const w=g(b,y-1);d[k]=i?f[w]*d[w]:f[k]*d[w]}}const m=e.makeTensorInfo(c.shape,h,d);if(l!=null){const b=tr(l),y=me({inputs:{x:m},backend:e,attrs:{perm:b}});return e.disposeIntermediateTensorInfo(m),e.disposeIntermediateTensorInfo(c),y}return m}const xT={kernelName:Bc,backendName:"cpu",kernelFunc:kT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function IT(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{axis:o,exclusive:i,reverse:a}=s;et(r,"cumsum");const l=Ce([o],r.shape.length);let c=r;l!=null&&(c=me({inputs:{x:r},backend:e,attrs:{perm:l}}));const u=Ye(1,r.shape.length)[0];if(u!==c.shape.length-1)throw new Error(`backend.cumsum in CPU expects an inner-most axis=${c.shape.length-1} but got axis=${u}`);const h=ms(c.dtype,"int32"),d=ie(Z(c.shape),h),f=e.data.get(c.dataId).values,p=c.shape[c.shape.length-1],g=a?(b,y)=>b+p-y-1:(b,y)=>b+y;for(let b=0;b<f.length;b+=p)for(let y=0;y<p;y++){const k=g(b,y);if(y===0)d[k]=i?0:f[k];else{const w=g(b,y-1);d[k]=i?f[w]+d[w]:f[k]+d[w]}}const m=e.makeTensorInfo(c.shape,h,d);if(l!=null){const b=tr(l),y=me({inputs:{x:m},backend:e,attrs:{perm:b}});return e.disposeIntermediateTensorInfo(m),e.disposeIntermediateTensorInfo(c),y}return m}const ST={kernelName:Ui,backendName:"cpu",kernelFunc:IT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function vT(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,weights:o}=t,{size:i,binaryOutput:a}=s;if(r.shape.length===1){const l=e.data.get(r.dataId).values,c=e.data.get(o.dataId).values,u=qp(l,c,o.dtype,o.shape,i);return e.makeTensorInfo([i],o.dtype,u)}else if(r.shape.length===2){const l=e.bufferSync(r),c=e.bufferSync(o),u=dN(l,c,i,a);return e.makeTensorInfo(u.shape,o.dtype,u.values)}throw new Error(`Error in denseBincount: input must be at most rank 2, but got rank${r.shape.length}.`)}const NT={kernelName:Wc,backendName:"cpu",kernelFunc:vT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function $T(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{blockSize:o,dataFormat:i}=s;v(i==="NHWC",()=>`Only NHWC dataFormat supported on CPU for depthToSpace. Got ${i}`);const a=r.shape[0],l=r.shape[1],c=r.shape[2],u=r.shape[3],h=l*o,d=c*o,f=u/(o*o),p=e.data.get(r.dataId).values,g=new Float32Array(a*h*d*f);let m=0;for(let b=0;b<a;++b)for(let y=0;y<h;++y){const k=Math.floor(y/o),w=y%o;for(let I=0;I<d;++I){const S=Math.floor(I/o),T=I%o,C=(w*o+T)*f;for(let N=0;N<f;++N){const x=N+C+u*(S+c*(k+l*b));g[m++]=p[x]}}}return e.makeTensorInfo([a,h,d,f],r.dtype,g)}const TT={kernelName:Gm,backendName:"cpu",kernelFunc:$T};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function fm(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,filter:o}=t,{strides:i,pad:a,dilations:l,dimRoundingMode:c}=s;et([r,o],"depthwiseConv2DNative");const u=it(r.shape),h=it(o.shape);let d=l;d==null&&(d=[1,1]),v(Ze(i,d),()=>`Error in depthwiseConv2d: Either strides or dilations must be 1. Got strides ${i} and dilations '${d}'`);const f=pn(r.shape,o.shape,i,d,a,c,!0),{filterHeight:p,filterWidth:g,dilationHeight:m,dilationWidth:b,padInfo:y}=f,k=y.left,w=y.top,I=f.outChannels/f.inChannels,S=new te(f.outShape,r.dtype),T=e.data.get(r.dataId).values,C=e.data.get(o.dataId).values,N=S.values;for(let $=0;$<f.batchSize;++$){const x=$*u[0],F=$*S.strides[0];for(let M=0;M<f.outHeight;++M){const O=F+M*S.strides[1],L=M*f.strideHeight-w;for(let B=0;B<p;++B){const G=L+B*m;if(G<0||G>=f.inHeight)continue;const W=B*h[0],V=x+G*u[1];for(let U=0;U<f.outWidth;++U){const q=O+U*S.strides[2],K=U*f.strideWidth-k;for(let j=0;j<g;++j){const Y=K+j*b;if(Y<0||Y>=f.inWidth)continue;const J=W+j*h[1],tt=V+Y*f.inChannels;let nt=q,at=J;for(let ot=0;ot<f.inChannels;++ot){const ht=T[tt+ot];for(let ft=0;ft<I;++ft)N[nt+ft]+=ht*C[at+ft];nt+=I,at+=I}}}}}}return e.makeTensorInfo(S.shape,S.dtype,S.values)}const CT={kernelName:Hi,backendName:"cpu",kernelFunc:fm};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function AT(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,dy:o}=t,{strides:i,dilations:a,pad:l,dimRoundingMode:c,filterShape:u}=s;et([r,o],"depthwiseConv2dNativeBackpropFilter");const h=pn(r.shape,u,i,a,l,c,!0),{strideHeight:d,strideWidth:f,filterHeight:p,filterWidth:g}=h,m=new te(h.filterShape,"float32"),b=h.padInfo.left,y=h.padInfo.top,k=h.outChannels/h.inChannels,w=e.data.get(r.dataId).values,I=new te(r.shape,r.dtype,w),S=e.data.get(o.dataId).values,T=new te(o.shape,o.dtype,S);for(let C=0;C<p;++C){const N=Math.max(0,Math.ceil((y-C)/d)),$=Math.min(h.outHeight,(h.inHeight+y-C)/d);for(let x=0;x<g;++x){const F=Math.max(0,Math.ceil((b-x)/f)),M=Math.min(h.outWidth,(h.inWidth+b-x)/f);for(let O=0;O<h.outChannels;++O){const L=Math.trunc(O/k),B=O%k;let G=0;for(let W=0;W<h.batchSize;++W)for(let V=N;V<$;++V){const U=C+V*d-y;for(let q=F;q<M;++q){const K=x+q*f-b;G+=I.get(W,U,K,L)*T.get(W,V,q,O)}}m.set(G,C,x,L,B)}}}return e.makeTensorInfo(m.shape,m.dtype,m.values)}const ET={kernelName:Vc,backendName:"cpu",kernelFunc:AT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function DT(n){const{inputs:t,backend:e,attrs:s}=n,{dy:r,filter:o}=t,{strides:i,dilations:a,pad:l,dimRoundingMode:c,inputShape:u}=s;et([r,o],"depthwiseConv2DNativeBackpropInput");const h=it(r.shape),d=it(o.shape),f=pn(u,o.shape,i,a,l,c,!0),p=new te(f.inShape,"float32"),g=p.values,[m,b,y]=p.strides,k=e.data.get(r.dataId).values,[w,I,S]=h,T=e.data.get(o.dataId).values,[C,N,$]=d,{batchSize:x,filterHeight:F,filterWidth:M,inChannels:O,inHeight:L,inWidth:B,outChannels:G,outHeight:W,outWidth:V,strideHeight:U,strideWidth:q}=f,K=F-1-f.padInfo.top,j=M-1-f.padInfo.left,Y=G/O;for(let J=0;J<x;++J)for(let tt=0;tt<O;++tt)for(let nt=0;nt<L;++nt){const at=nt-K,ot=Math.max(0,Math.ceil(at/U)),ht=Math.min(W,(F+at)/U);for(let ft=0;ft<B;++ft){const St=ft-j,Et=Math.max(0,Math.ceil(St/q)),Pt=Math.min(V,(M+St)/q);let Dt=0;for(let vt=ot;vt<ht;++vt){const _t=vt*U-at;for(let Lt=Et;Lt<Pt;++Lt){const kn=Lt*q-St,re=w*J+I*vt+S*Lt,Vn=C*(F-1-_t)+N*(M-1-kn)+$*tt;for(let ve=0;ve<Y;++ve){const hs=tt*Y+ve,qe=k[re+hs],xn=T[Vn+ve];Dt+=qe*xn}}}g[m*J+b*nt+y*ft+tt]=Dt}}return e.makeTensorInfo(p.shape,p.dtype,p.values)}const FT={kernelName:Gc,backendName:"cpu",kernelFunc:DT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function MT(n){const{inputs:t,backend:e}=n,{x:s}=t,r=Z(s.shape),o=e.data.get(s.dataId).values,i=mt([r,r],s.dtype),a=i.values;for(let c=0;c<o.length;c++)a[c*r+c]=o[c];const l=[...s.shape,...s.shape];return e.makeTensorInfo(l,i.dtype,i.values)}const RT={kernelName:Um,backendName:"cpu",kernelFunc:MT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const zT={kernelName:Uc,backendName:"cpu",kernelFunc:({inputs:n,backend:t,attrs:e})=>{const{x:s,filter:r}=n,{strides:o,pad:i,dilations:a}=e,l=t,c=l.data.get(s.dataId).values,u=s.shape.length,h=l.data.get(r.dataId).values,d=r.shape.length,{batchSize:f,inHeight:p,inWidth:g,inChannels:m,outHeight:b,outWidth:y,padInfo:k,strideHeight:w,strideWidth:I,filterHeight:S,filterWidth:T,dilationHeight:C,dilationWidth:N,outShape:$}=nl(s.shape,r.shape,o,i,"NHWC",a),x=Z($),F=$.length,M=Gt(s.dtype,x);for(let L=0;L<f;++L)for(let B=0;B<b;++B){const G=B*w-k.top;for(let W=0;W<y;++W){const V=W*I-k.left;for(let U=0;U<m;++U){let q=Number.MIN_SAFE_INTEGER;for(let j=0;j<S;++j){const Y=G+j*C;if(Y>=0&&Y<p)for(let J=0;J<T;++J){const tt=V+J*N;if(tt>=0&&tt<g){const nt=je([L,Y,tt,U],u,it(s.shape)),at=je([j,J,U],d,it(r.shape)),ot=c[nt]+h[at];ot>q&&(q=ot)}}}const K=je([L,B,W,U],F,it($));M[K]=q}}}return{dataId:l.write(Kn(M,s.dtype),$,s.dtype),shape:$,dtype:s.dtype}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const LT={kernelName:ji,backendName:"cpu",kernelFunc:({inputs:n,backend:t,attrs:e})=>{const{x:s,filter:r,dy:o}=n,{strides:i,pad:a,dilations:l}=e,c=t,u=Le(s.shape,c.data.get(s.dataId).values),h=Le(r.shape,c.data.get(r.dataId).values),{batchSize:d,inHeight:f,inWidth:p,inChannels:g,outHeight:m,outWidth:b,padInfo:y,strideHeight:k,strideWidth:w,filterHeight:I,filterWidth:S,dilationHeight:T,dilationWidth:C,outShape:N}=nl(s.shape,r.shape,i,a,"NHWC",l);v(o.rank===N.length,()=>`Error in ${ji}, dy must have the same rank as output ${N.length}, but got ${o.rank}`);const $=Le(N,c.data.get(o.dataId).values),x=Sc(r.shape,r.dtype);for(let M=0;M<d;++M)for(let O=0;O<m;++O){const L=O*k-y.top;for(let B=0;B<b;++B){const G=B*w-y.left;for(let W=0;W<g;++W){let V=Number.MIN_SAFE_INTEGER,U=0,q=0;for(let K=0;K<I;++K){const j=L+K*T;if(j>=0&&j<f)for(let Y=0;Y<S;++Y){const J=G+Y*C;if(J>=0&&J<p){const tt=u[M][j][J][W]+h[K][Y][W];tt>V&&(V=tt,U=K,q=Y)}}}x[U][q][W]+=$[M][O][B][W]}}}return{dataId:c.write(Kn(x,s.dtype),r.shape,r.dtype),shape:r.shape,dtype:r.dtype}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const OT={kernelName:qi,backendName:"cpu",kernelFunc:({inputs:n,backend:t,attrs:e})=>{const{x:s,filter:r,dy:o}=n,{strides:i,pad:a,dilations:l}=e,c=t,u=Le(s.shape,c.data.get(s.dataId).values),h=Le(r.shape,c.data.get(r.dataId).values),{batchSize:d,inHeight:f,inWidth:p,inChannels:g,outHeight:m,outWidth:b,padInfo:y,strideHeight:k,strideWidth:w,filterHeight:I,filterWidth:S,dilationHeight:T,dilationWidth:C,outShape:N}=nl(s.shape,r.shape,i,a,"NHWC",l);v(o.rank===N.length,()=>`Error in ${qi}, dy must have the same rank as output ${N.length}, but got ${o.rank}`);const $=Le(N,c.data.get(o.dataId).values),x=Sc(s.shape,s.dtype);for(let M=0;M<d;++M)for(let O=0;O<m;++O){const L=O*k-y.top;for(let B=0;B<b;++B){const G=B*w-y.left;for(let W=0;W<g;++W){let V=Number.MIN_SAFE_INTEGER,U=L<0?0:L,q=G<0?0:G;for(let K=0;K<I;++K){const j=L+K*T;if(j>=0&&j<f)for(let Y=0;Y<S;++Y){const J=G+Y*C;if(J>=0&&J<p){const tt=u[M][j][J][W]+h[K][Y][W];tt>V&&(V=tt,U=j,q=J)}}}x[M][U][q][W]+=$[M][O][B][W]}}}return{dataId:c.write(Kn(x,s.dtype),s.shape,s.dtype),shape:s.shape,dtype:s.dtype}}};/**
 * @license
 * Copyright 2023 Google LLC.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function _T(n){const{inputs:t,backend:e,attrs:s}=n,{image:r}=t,{canvas:o,options:i}=s,{contextOptions:a,imageOptions:l}=i||{},c=(l==null?void 0:l.alpha)||1,u=(a==null?void 0:a.contextType)||"2d";if(u!=="2d")throw new Error(`Context type ${a.contextType} is not supported by the CPU backend.`);const h=o.getContext(u,(a==null?void 0:a.contextAttributes)||{});if(h==null)throw new Error(`Could not get the context with ${u} type.`);const[d,f]=r.shape.slice(0,2),p=r.shape.length===2?1:r.shape[2],g=e.data.get(r.dataId).values,m=r.dtype==="float32"?255:1,b=new Uint8ClampedArray(f*d*4);for(let k=0;k<d*f;++k){const w=[0,0,0,255*c];for(let S=0;S<p;S++){const T=g[k*p+S];if(r.dtype==="float32"){if(T<0||T>1)throw new Error(`Tensor values for a float32 Tensor must be in the range [0 - 1] but encountered ${T}.`)}else if(r.dtype==="int32"&&(T<0||T>255))throw new Error(`Tensor values for a int32 Tensor must be in the range [0 - 255] but encountered ${T}.`);p===1?(w[0]=T*m,w[1]=T*m,w[2]=T*m):w[S]=T*m}const I=k*4;b[I+0]=Math.round(w[0]),b[I+1]=Math.round(w[1]),b[I+2]=Math.round(w[2]),b[I+3]=Math.round(w[3])}o.width=f,o.height=d;const y=new ImageData(b,f,d);return h.putImageData(y,0,0),r}const BT={kernelName:Hm,backendName:"cpu",kernelFunc:_T};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function Sr(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{axis:o,keepDims:i}=s;et(r,"sum");let a;r.dtype==="bool"?a=Bn({inputs:{x:r},backend:e,attrs:{dtype:"int32"}}):a=hn({inputs:{x:r},backend:e});const l=a.shape.length,c=Ft(o,a.shape),u=Ce(c,l);let h=c,d=a;u!=null&&(d=me({inputs:{x:a},backend:e,attrs:{perm:u}}),h=Ye(h.length,l)),ts("sum",h,d.shape.length);const[f,p]=Je(d.shape,h),g=ms(d.dtype,"int32");let m=ci(e,f,g);const b=Z(p),y=e.data.get(m.dataId).values,k=e.data.get(d.dataId).values;for(let w=0;w<y.length;++w){const I=w*b;let S=0;for(let T=0;T<b;++T)S+=k[I+T];y[w]=S}if(i){const w=Te(m.shape,c),I=m;m=At({inputs:{x:m},backend:e,attrs:{shape:w}}),e.disposeIntermediateTensorInfo(I)}return e.disposeIntermediateTensorInfo(a),u!=null&&e.disposeIntermediateTensorInfo(d),m}const PT={kernelName:Aa,backendName:"cpu",kernelFunc:Sr};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function WT(n){const{inputs:t,backend:e,attrs:s}=n,{equation:r}=s,o=t,{allDims:i,summedDims:a,idDims:l}=zk(r,o.length);Ok(i.length,l,o);const{path:c,steps:u}=_k(a,l),h=u.length;let d=null,f=i.length;const p=[];for(let g=0;g<h;++g){for(const m of u[g]){const{permutationIndices:b,expandDims:y}=Lk(f,l[m]);let k;Bk(b)?k=o[m]:(k=me({inputs:{x:o[m]},backend:e,attrs:{perm:b}}),p.push(k));const w=k.shape.slice();for(let I=0;I<y.length;++I)w.splice(y[I],0,1);oe(k.shape,w)||(k=At({inputs:{x:k},backend:e,attrs:{shape:w}}),p.push(k)),d===null?d=k:(d=ui({inputs:{a:k,b:d},backend:e}),p.push(d))}g<h-1&&(c[g]>=0&&(d=Sr({inputs:{x:d},backend:e,attrs:{axis:c[g]-(i.length-f),keepDims:!1}}),p.push(d)),f--)}for(const g of p)g!==d&&e.disposeIntermediateTensorInfo(g);return d}const VT={kernelName:Hc,backendName:"cpu",kernelFunc:WT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function GT(n){const{inputs:t,backend:e}=n,{dy:s,y:r}=t;et([s,r],"eluGrad");const o=new Float32Array(Z(r.shape)),i=e.data.get(r.dataId).values,a=e.data.get(s.dataId).values;for(let l=0;l<i.length;++l){const c=i[l];c>=0?o[l]=a[l]:o[l]=a[l]*(c+1)}return e.makeTensorInfo(r.shape,"float32",o)}const UT={kernelName:qc,backendName:"cpu",kernelFunc:GT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const HT=Ik,qT=Sk,jT=vk,KT=Nk,XT=$k,ZT=Tk,JT=It(zr,n=>{const t=Math.sign(n),e=Math.abs(n),s=1/(1+HT*e);return t*(1-((((ZT*s+XT)*s+KT)*s+jT)*s+qT)*s*Math.exp(-e*e))}),YT={kernelName:zr,backendName:"cpu",kernelFunc:JT};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function fi(n){const{inputs:t,backend:e,attrs:s}=n,{input:r}=t,{dim:o}=s,i=r.shape.length,a=r.shape.slice();let l=o;return o<0&&(v(-(i+1)<=o,()=>`Axis must be in the interval [${-(i+1)}, ${i}]`),l=i+o+1),a.splice(l,0,1),At({inputs:{x:r},backend:e,attrs:{shape:a}})}const QT={kernelName:Xi,backendName:"cpu",kernelFunc:fi};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const tC=Vt((n,t)=>n/t),dc=Xt(Mr,tC),fc={kernelName:Mr,backendName:"cpu",kernelFunc:dc};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function pm(n,t,e){const s=n.shape,r=s[0],o=s[1],i=e.data.get(n.dataId),a=i.complexTensorInfos.real,l=i.complexTensorInfos.imag,c=[r,o],u=Z(c),h=he("float32",u),d=he("float32",u);for(let m=0;m<r;m++){const b=us({inputs:{x:a},backend:e,attrs:{begin:[m,0],size:[1,o]}}),y=us({inputs:{x:l},backend:e,attrs:{begin:[m,0],size:[1,o]}}),k=Ie({inputs:{real:b,imag:y},backend:e}),{real:w,imag:I}=eC(k,t,e),S=Ds(w,I);for(let T=0;T<o;T++){const C=Zh(S,T);h[m*o+T]=C.real,d[m*o+T]=C.imag}e.disposeIntermediateTensorInfo(b),e.disposeIntermediateTensorInfo(y),e.disposeIntermediateTensorInfo(k)}const f=e.makeTensorInfo(c,"float32",h),p=e.makeTensorInfo(c,"float32",d),g=Ie({inputs:{real:f,imag:p},backend:e});return e.disposeIntermediateTensorInfo(f),e.disposeIntermediateTensorInfo(p),g}function eC(n,t,e){const s=Z(n.shape),r=e.data.get(n.dataId),o=e.data.get(r.complexTensorInfos.real.dataId).values,i=e.data.get(r.complexTensorInfos.imag.dataId).values;if(nC(s)){const a=pc(o,i,s,t,e),l=[n.shape[0],n.shape[1]];if(t){const c=e.makeTensorInfo(l,"float32",a.real),u=e.makeTensorInfo(l,"float32",a.imag),h=e.makeTensorInfo([],"float32",Ga(s,"float32")),d=hn({inputs:{x:h},backend:e}),f=fc.kernelFunc({inputs:{a:c,b:h},backend:e}),p=fc.kernelFunc({inputs:{a:u,b:d},backend:e}),g=e.data.get(f.dataId).values,m=e.data.get(p.dataId).values;return e.disposeIntermediateTensorInfo(c),e.disposeIntermediateTensorInfo(u),e.disposeIntermediateTensorInfo(h),e.disposeIntermediateTensorInfo(d),e.disposeIntermediateTensorInfo(f),e.disposeIntermediateTensorInfo(p),{real:g,imag:m}}return a}else{const a=Ds(o,i),l=sC(a,s,t);return Ck(l)}}function nC(n){return(n&n-1)===0}function pc(n,t,e,s,r){if(e===1)return{real:n,imag:t};const o=Ds(n,t),i=e/2,a=Ak(o),l=a.real,c=a.imag,u=[l.length],h=r.makeTensorInfo(u,"float32",l),d=r.makeTensorInfo(u,"float32",c),f=Ie({inputs:{real:h,imag:d},backend:r}),p=Ek(o),g=p.real,m=p.imag,b=[g.length],y=r.makeTensorInfo(b,"float32",g),k=r.makeTensorInfo(b,"float32",m),w=Ie({inputs:{real:y,imag:k},backend:r}),I=pc(l,c,i,s,r),S=I.real,T=I.imag,C=[S.length],N=r.makeTensorInfo(C,"float32",S),$=r.makeTensorInfo(C,"float32",T),x=Ie({inputs:{real:N,imag:$},backend:r}),F=pc(g,m,i,s,r),M=F.real,O=F.imag,L=[M.length],B=r.makeTensorInfo(L,"float32",M),G=r.makeTensorInfo(L,"float32",O),W=Ie({inputs:{real:B,imag:G},backend:r}),V=Fk(e,s),U=[V.real.length],q=r.makeTensorInfo(U,"float32",V.real),K=r.makeTensorInfo(U,"float32",V.imag),j=Ie({inputs:{real:q,imag:K},backend:r}),Y=ui({inputs:{a:j,b:W},backend:r}),J=Os({inputs:{a:x,b:Y},backend:r}),tt=uc({inputs:{a:x,b:Y},backend:r}),nt=cs({inputs:{input:J},backend:r}),at=cs({inputs:{input:tt},backend:r}),ot=Bs({inputs:{input:J},backend:r}),ht=Bs({inputs:{input:tt},backend:r}),ft=Ps({inputs:[nt,at],backend:r,attrs:{axis:0}}),St=Ps({inputs:[ot,ht],backend:r,attrs:{axis:0}}),Et=r.data.get(ft.dataId).values,Pt=r.data.get(St.dataId).values;return r.disposeIntermediateTensorInfo(h),r.disposeIntermediateTensorInfo(d),r.disposeIntermediateTensorInfo(f),r.disposeIntermediateTensorInfo(y),r.disposeIntermediateTensorInfo(k),r.disposeIntermediateTensorInfo(w),r.disposeIntermediateTensorInfo(N),r.disposeIntermediateTensorInfo($),r.disposeIntermediateTensorInfo(x),r.disposeIntermediateTensorInfo(B),r.disposeIntermediateTensorInfo(G),r.disposeIntermediateTensorInfo(W),r.disposeIntermediateTensorInfo(q),r.disposeIntermediateTensorInfo(K),r.disposeIntermediateTensorInfo(j),r.disposeIntermediateTensorInfo(Y),r.disposeIntermediateTensorInfo(J),r.disposeIntermediateTensorInfo(tt),r.disposeIntermediateTensorInfo(nt),r.disposeIntermediateTensorInfo(ot),r.disposeIntermediateTensorInfo(at),r.disposeIntermediateTensorInfo(ht),r.disposeIntermediateTensorInfo(ft),r.disposeIntermediateTensorInfo(St),{real:Et,imag:Pt}}function sC(n,t,e){const s=new Float32Array(t*2);for(let r=0;r<t;r++){let o=0,i=0;for(let a=0;a<t;a++){const l=Mk(r*a,t,e),c=Zh(n,a);o+=c.real*l.real-c.imag*l.imag,i+=c.real*l.imag+c.imag*l.real}e&&(o/=t,i/=t),Dk(s,o,i,r)}return s}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function rC(n){const{inputs:t,backend:e}=n,{input:s}=t,r=Z(s.shape),o=s.shape[s.shape.length-1],i=r/o,a=At({inputs:{x:s},backend:e,attrs:{shape:[i,o]}}),l=pm(a,!1,e),c=At({inputs:{x:l},backend:e,attrs:{shape:s.shape}});return e.disposeIntermediateTensorInfo(a),e.disposeIntermediateTensorInfo(l),c}const oC={kernelName:qm,backendName:"cpu",kernelFunc:rC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function mc(n){const{backend:t,attrs:e}=n,{shape:s,value:r,dtype:o}=e,i=o||Ws(r),a=Gt(i,Z(s));return aC(a,r,i),t.makeTensorInfo(s,i,a)}const iC={kernelName:jc,backendName:"cpu",kernelFunc:mc};function aC(n,t,e){n.fill(t)}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const lC={kernelName:Kc,backendName:"cpu",kernelFunc:({inputs:n,attrs:t,backend:e})=>{const{image:s}=n,r=e,o=he(s.dtype,Z(s.shape)),[i,a,l,c]=s.shape,u=r.data.get(s.dataId).values;for(let d=0;d<i;d++){const f=d*l*a*c;for(let p=0;p<a;p++){const g=p*(l*c);for(let m=0;m<l;m++){const b=m*c;for(let y=0;y<c;y++){const k=Math.round(l-m-1),w=f+g+b+y;let I=u[w];if(k>=0&&k<l){const S=k*c,T=f+g+S+y;I=u[T]}o[w]=I}}}}return{dataId:r.write(o,s.shape,s.dtype),shape:s.shape,dtype:s.dtype}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function cC(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,filter:o,bias:i,preluActivationWeights:a}=t,{strides:l,pad:c,dataFormat:u,dilations:h,dimRoundingMode:d,activation:f,leakyreluAlpha:p}=s;let g=dm({inputs:{x:r,filter:o},backend:e,attrs:{strides:l,pad:c,dataFormat:u,dilations:h,dimRoundingMode:d}});if(i){const m=g;if(u==="NCHW"&&i.shape.length===1&&i.shape[0]!==1){const b=At({inputs:{x:i},backend:e,attrs:{shape:[i.shape[0],1,1]}});g=Os({inputs:{a:g,b},backend:e}),e.disposeIntermediateTensorInfo(b)}else g=Os({inputs:{a:g,b:i},backend:e});e.disposeIntermediateTensorInfo(m)}if(f){const m=g;if(u==="NCHW"&&f==="prelu"&&a.shape.length===1&&a.shape[0]!==1){const b=At({inputs:{x:a},backend:e,attrs:{shape:[a.shape[0],1,1]}});g=di(e,g,f,b,p),e.disposeIntermediateTensorInfo(b)}else g=di(e,g,f,a,p);e.disposeIntermediateTensorInfo(m)}return g}const uC={kernelName:Ba,backendName:"cpu",kernelFunc:cC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function hC(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,filter:o,bias:i,preluActivationWeights:a}=t,{strides:l,pad:c,dataFormat:u,dilations:h,dimRoundingMode:d,activation:f,leakyreluAlpha:p}=s;let g=fm({inputs:{x:r,filter:o},backend:e,attrs:{strides:l,pad:c,dataFormat:u,dilations:h,dimRoundingMode:d}});if(i){const m=g;g=Os({inputs:{a:g,b:i},backend:e}),e.disposeIntermediateTensorInfo(m)}if(f){const m=g;g=di(e,g,f,a,p),e.disposeIntermediateTensorInfo(m)}return g}const dC={kernelName:gg,backendName:"cpu",kernelFunc:hC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function fC(n){const{inputs:t,backend:e}=n,{params:s,indices:r}=t,o=Z(s.shape),i=r.shape,a=i[i.length-1],[l,c,u,h]=sk(s,r);if(c===0)return e.makeTensorInfo(l,s.dtype,[]);const d=e.data.get(r.dataId).values,f=e.bufferSync(s),p=MN(d,f,s.dtype,c,a,u,h,s.shape,o);return e.makeTensorInfo(l,s.dtype,p.values)}const pC={kernelName:jm,backendName:"cpu",kernelFunc:fC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function mC(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,indices:o}=t,{axis:i,batchDims:a}=s;et([r,o],"gatherV2");const l=Ft(i,r.shape)[0],c=e.data.get(o.dataId).values,u=r.shape[l];for(let w=0;w<c.length;++w){const I=c[w];v(I<=u-1&&I>=0,()=>`GatherV2: the index value ${I} is not in [0, ${u-1}]`)}let h=a;a==null&&(h=0);const d=Z(o.shape),f=Qk(r,o,l,h),p=At({inputs:{x:r},backend:e,attrs:{shape:[f.batchSize,f.outerSize,f.dimSize,f.sliceSize]}}),g=At({inputs:{x:o},backend:e,attrs:{shape:[f.batchSize,d/f.batchSize]}}),m=[f.batchSize,f.outerSize,d/f.batchSize,f.sliceSize],b=e.bufferSync(g),y=e.bufferSync(p),k=RN(y,b,m);return e.disposeIntermediateTensorInfo(p),e.disposeIntermediateTensorInfo(g),e.makeTensorInfo(f.outputShape,k.dtype,k.values)}const gC={kernelName:Yi,backendName:"cpu",kernelFunc:mC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function bC(n){const{inputs:t,backend:e}=n,{input:s}=t,r=Z(s.shape),o=s.shape[s.shape.length-1],i=r/o,a=At({inputs:{x:s},backend:e,attrs:{shape:[i,o]}}),l=pm(a,!0,e),c=At({inputs:{x:l},backend:e,attrs:{shape:s.shape}});return e.disposeIntermediateTensorInfo(a),e.disposeIntermediateTensorInfo(l),c}const yC={kernelName:Km,backendName:"cpu",kernelFunc:bC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const wC=It(ta,n=>Number.isFinite(n)?1:0,"bool"),kC={kernelName:ta,backendName:"cpu",kernelFunc:wC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const xC=It(ea,n=>Math.abs(n)===1/0?1:0,"bool"),IC={kernelName:ea,backendName:"cpu",kernelFunc:xC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const SC=It(na,n=>Number.isNaN(n)?1:0,"bool"),vC={kernelName:na,backendName:"cpu",kernelFunc:SC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function NC(n){const{backend:t,attrs:e}=n,{start:s,stop:r,num:o}=e,i=jN(s,r,o);return t.makeTensorInfo([i.length],"float32",i)}const $C={kernelName:Xm,backendName:"cpu",kernelFunc:NC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const TC=It(Vr,n=>Math.log1p(n)),CC={kernelName:Vr,backendName:"cpu",kernelFunc:TC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const AC=Vt((n,t)=>n&&t),EC=Xt(ia,AC,null,"bool"),DC={kernelName:ia,backendName:"cpu",kernelFunc:EC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const FC=It(aa,n=>n?0:1,"bool"),MC={kernelName:aa,backendName:"cpu",kernelFunc:FC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const RC=Vt((n,t)=>n||t),zC=Xt(Zc,RC,null,"bool"),LC={kernelName:Zc,backendName:"cpu",kernelFunc:zC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function OC(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{depthRadius:o,bias:i,alpha:a,beta:l}=s;et(r,"LRN");const c=r.shape[3],u=c-1,h=e.data.get(r.dataId).values,d=Z(r.shape),f=new Float32Array(d);function p(g){const m=g%c;let b=g-m+Math.max(0,m-o);const y=g-m+Math.min(m+o,u);let k=0;for(;b<=y;b++){const w=h[b];k+=w*w}return k}for(let g=0;g<d;g++){const m=p(g),b=h[g]*Math.pow(i+a*m,-l);f[g]=b}return e.makeTensorInfo(r.shape,r.dtype,f)}const _C={kernelName:Jc,backendName:"cpu",kernelFunc:OC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function BC(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,y:o,dy:i}=t,{depthRadius:a,bias:l,alpha:c,beta:u}=s;et(i,"LRNGrad");const h=Z(i.shape),d=i.shape[3],f=e.data.get(i.dataId).values,p=e.data.get(r.dataId).values,g=e.data.get(o.dataId).values,m=new Float32Array(h),b=h;for(let y=0;y<b;y++){const k=y%d,w=y-k+Math.max(0,k-a),I=y-k+Math.min(d,k+a+1);let S=0;for(let T=w;T<I;T++)S+=Math.pow(p[T],2);S=c*S+l;for(let T=w;T<I;T++){let C=-2*c*u*p[T]*g[y]/S;y===T&&(C+=Math.pow(S,-u)),C*=f[y],m[T]+=C}}return e.makeTensorInfo(i.shape,r.dtype,m)}const PC={kernelName:Yc,backendName:"cpu",kernelFunc:BC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function mm(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{reductionIndices:o,keepDims:i}=s,a=e;let l=r.shape;const c=l.length,u=Ft(o,l);let h=u;const d=Ce(h,c);let f=a.data.get(r.dataId).values;if(d!=null){const w=new Array(c);for(let I=0;I<w.length;I++)w[I]=l[d[I]];f=Zp(f,l,r.dtype,d,w),h=Ye(h.length,c),l=w}et(r,"max"),ts("max",h,c);const[p,g]=Je(l,h),m=Z(g),b=JN(f,m,p,r.dtype),y=a.write(b,p,r.dtype);let k=p;return i&&(k=Te(p,u)),{dataId:y,shape:k,dtype:r.dtype}}const WC={kernelName:la,backendName:"cpu",kernelFunc:mm};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function VC(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t;et(r,"maxPool");const{filterSize:o,strides:i,pad:a,dimRoundingMode:l}=s,c=1;v(Ze(i,c),()=>`Error in maxPool: Either strides or dilations must be 1. Got strides ${i} and dilations '${c}'`);const u=Zs(r.shape,o,i,c,a,l);let h;if(u.filterWidth===1&&u.filterHeight===1&&oe(u.inShape,u.outShape))h=hn({inputs:{x:r},backend:e});else{const d=e.data.get(r.dataId).values,f=it(r.shape),p=hc(d,r.shape,r.dtype,f,u,"max");h=e.makeTensorInfo(u.outShape,r.dtype,p.values)}return h}const GC={kernelName:ca,backendName:"cpu",kernelFunc:VC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function UC(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{filterSize:o,strides:i,pad:a,dimRoundingMode:l,dataFormat:c}=s;et(r,"maxPool3d");const u=yo(r.shape,o,i,1,a,l,c),h=e.data.get(r.dataId).values,d=hm(h,r.shape,r.dtype,it(r.shape),u,"max");return e.makeTensorInfo(d.shape,"float32",d.values)}const HC={kernelName:ua,backendName:"cpu",kernelFunc:UC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function qC(n){const{inputs:t,backend:e,attrs:s}=n,{dy:r,input:o}=t,{filterSize:i,strides:a,pad:l,dimRoundingMode:c}=s;et([r,o],"maxPool3DGrad");const u=yo(o.shape,i,a,1,l,c),h=e.bufferSync(o),d=z$(h,u),f=u.strideDepth,p=u.strideHeight,g=u.strideWidth,m=u.dilationDepth,b=u.dilationHeight,y=u.dilationWidth,k=u.effectiveFilterDepth,w=u.effectiveFilterHeight,I=u.effectiveFilterWidth,S=k-1-u.padInfo.front,T=I-1-u.padInfo.left,C=w-1-u.padInfo.top,N=mt(o.shape,"float32"),$=e.bufferSync(r);for(let x=0;x<u.batchSize;++x)for(let F=0;F<u.inChannels;++F)for(let M=0;M<u.inDepth;++M)for(let O=0;O<u.inHeight;++O)for(let L=0;L<u.inWidth;++L){const B=M-S,G=O-C,W=L-T;let V=0;for(let U=0;U<k;U+=m){const q=(B+U)/f;if(!(q<0||q>=u.outDepth||Math.floor(q)!==q))for(let K=0;K<w;K+=b){const j=(G+K)/p;if(!(j<0||j>=u.outHeight||Math.floor(j)!==j))for(let Y=0;Y<I;Y+=y){const J=(W+Y)/g;if(J<0||J>=u.outWidth||Math.floor(J)!==J)continue;const tt=k*w*I-1-d.get(x,q,j,J,F),nt=U*w*I+K*I+Y,at=tt===nt?1:0;if(at===0)continue;const ot=$.get(x,q,j,J,F);V+=ot*at}}}N.set(V,x,M,O,L,F)}return e.makeTensorInfo(N.shape,N.dtype,N.values)}const jC={kernelName:tu,backendName:"cpu",kernelFunc:qC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function KC(n){const{inputs:t,backend:e,attrs:s}=n,{dy:r,input:o,output:i}=t,a=o;et([o,i],"maxPoolGrad");const{filterSize:l,strides:c,pad:u,dimRoundingMode:h}=s,d=Zs(a.shape,l,c,1,u,h),f=e.data.get(a.dataId).values,p=mt(d.outShape,a.dtype,um(f,a.shape,a.dtype,d).values),g=d.strideHeight,m=d.strideWidth,b=d.dilationHeight,y=d.dilationWidth,k=d.effectiveFilterHeight,w=d.effectiveFilterWidth,I=w-1-d.padInfo.left,S=k-1-d.padInfo.top,T=mt(a.shape,"float32"),C=e.data.get(r.dataId).values,N=mt(r.shape,"float32",C);for(let $=0;$<d.batchSize;++$)for(let x=0;x<d.inChannels;++x)for(let F=0;F<d.inHeight;++F)for(let M=0;M<d.inWidth;++M){const O=F-S,L=M-I;let B=0;for(let G=0;G<k;G+=b){const W=(O+G)/g;if(!(W<0||W>=d.outHeight||Math.floor(W)!==W))for(let V=0;V<w;V+=y){const U=(L+V)/m;if(U<0||U>=d.outWidth||Math.floor(U)!==U)continue;const q=k*w-1-p.get($,W,U,x),K=G*w+V,j=q===K?1:0;if(j===0)continue;const Y=N.get($,W,U,x);B+=Y*j}}T.set(B,$,F,M,x)}return e.makeTensorInfo(T.shape,T.dtype,T.values)}const XC={kernelName:Qc,backendName:"cpu",kernelFunc:KC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function ZC(n,t,e,s,r){const o=it(t),i=hc(n,t,e,o,r,"max"),a=um(n,t,e,r,!0,s);return[i.values,a.values]}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const JC={kernelName:Jm,backendName:"cpu",kernelFunc:({inputs:n,attrs:t,backend:e})=>{const{x:s}=n,{filterSize:r,strides:o,pad:i,includeBatchInIndex:a}=t,l=e;et(s,"MaxPoolWithArgmax");const c=l.data.get(s.dataId).values,u=Zs(s.shape,r,o,[1,1],i),[h,d]=ZC(c,s.shape,s.dtype,a,u),f=l.write(h,u.outShape,s.dtype),p=l.write(d,u.outShape,s.dtype);return[{dataId:f,shape:u.outShape,dtype:s.dtype},{dataId:p,shape:u.outShape,dtype:"int32"}]}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function YC(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{axis:o,keepDims:i}=s,a=Ft(o,r.shape),c=Je(r.shape,a)[1],u=Z(c),h=[],d=e.makeTensorInfo([],"float32",new Float32Array([u]));h.push(d);const f=Bn({inputs:{x:r},backend:e,attrs:{dtype:"float32"}});h.push(f);const p=dc({inputs:{a:f,b:d},backend:e});h.push(p);const g=Sr({inputs:{x:p},backend:e,attrs:{axis:o,keepDims:i}});return h.forEach(m=>e.disposeIntermediateTensorInfo(m)),g}const QC={kernelName:ha,backendName:"cpu",kernelFunc:YC};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function tA(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{axis:o,keepDims:i}=s;et(r,"min");const a=Ft(o,r.shape);let l=a;const c=Ce(l,r.shape.length);let u=r;c!=null&&(u=me({inputs:{x:r},backend:e,attrs:{perm:c}}),l=Ye(l.length,r.shape.length)),ts("min",l,u.shape.length);const[h,d]=Je(u.shape,l),f=Z(d),p=ie(Z(h),u.dtype),g=e.data.get(u.dataId).values;for(let b=0;b<p.length;++b){const y=b*f;let k=g[y];for(let w=0;w<f;++w){const I=g[y+w];(Number.isNaN(I)||I<k)&&(k=I)}p[b]=k}c!=null&&e.disposeIntermediateTensorInfo(u);const m=e.makeTensorInfo(h,u.dtype,p);if(i){const b=Te(h,a),y=At({inputs:{x:m},backend:e,attrs:{shape:b}});return e.disposeIntermediateTensorInfo(m),y}return m}const eA={kernelName:da,backendName:"cpu",kernelFunc:tA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function nA(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{paddings:o,mode:i}=s;et(r,"mirrorPad");const a=o.map((k,w)=>k[0]+r.shape[w]+k[1]),l=o.map(k=>k[0]),c=o.map((k,w)=>k[0]+r.shape[w]),u=i==="reflect"?0:1,h=e.data.get(r.dataId).values,d=r.shape.length,f=it(r.shape),p=Z(a),g=a.length,m=it(a),b=he(r.dtype,p);for(let k=0;k<p;k++){let w=fs(k,g,m);for(let S=0;S<g;S++)w[S]<l[S]?w[S]=l[S]*2-w[S]-u:w[S]>=c[S]&&(w[S]=(c[S]-1)*2-w[S]+u);w=w.map((S,T)=>S-l[T]);const I=je(w,d,f);b[k]=h[I]}return{dataId:e.write(b,a,r.dtype),shape:a,dtype:r.dtype}}const sA={kernelName:eu,backendName:"cpu",kernelFunc:nA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const rA=Vt(((n,t)=>{const e=n%t;return n<0&&t<0||n>=0&&t>=0?e:(e+t)%t})),oA=Xt(fa,rA),iA={kernelName:fa,backendName:"cpu",kernelFunc:oA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function gm(n){const{inputs:t,backend:e,attrs:s}=n,{logits:r}=t,{dim:o}=s,i=r.shape.length;let a=o;if(a===-1&&(a=i-1),a!==i-1)throw Error(`Softmax along a non-last dimension is not yet supported. Logits was rank ${i} and dim was ${a}`);const l=Ft([a],r.shape),c=mm({inputs:{x:r},backend:e,attrs:{reductionIndices:l,keepDims:!1}}),u=Te(c.shape,l),h=At({inputs:{x:c},backend:e,attrs:{shape:u}}),d=uc({inputs:{a:r,b:h},backend:e}),f=Kp({inputs:{x:d},backend:e}),p=Sr({inputs:{x:f},backend:e,attrs:{axis:l,keepDims:!1}}),g=At({inputs:{x:p},backend:e,attrs:{shape:u}}),m=dc({inputs:{a:f,b:g},backend:e});return e.disposeIntermediateTensorInfo(c),e.disposeIntermediateTensorInfo(h),e.disposeIntermediateTensorInfo(d),e.disposeIntermediateTensorInfo(f),e.disposeIntermediateTensorInfo(p),e.disposeIntermediateTensorInfo(g),m}const aA={kernelName:Fa,backendName:"cpu",kernelFunc:gm};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function lA(n){const{inputs:t,backend:e,attrs:s}=n,{logits:r}=t,{numSamples:o,seed:i,normalized:a}=s;et(r,"multinomial");const l=a?r:gm({inputs:{logits:r},backend:e,attrs:{dim:-1}}),c=l.shape[0],u=l.shape[1],h=e.data.get(l.dataId).values,d=[c,o],f=ie(Z(d),"int32");for(let p=0;p<c;++p){const g=p*u,m=new Float32Array(u-1);m[0]=h[g];for(let k=1;k<m.length;++k)m[k]=m[k-1]+h[g+k];const b=ml.alea(i.toString()),y=p*o;for(let k=0;k<o;++k){const w=b();f[y+k]=m.length;for(let I=0;I<m.length;I++)if(w<m[I]){f[y+k]=I;break}}}return a||e.disposeIntermediateTensorInfo(l),e.makeTensorInfo(d,"int32",f)}const cA={kernelName:Ym,backendName:"cpu",kernelFunc:lA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const uA=Ch;function hA(n){const{inputs:t,backend:e,attrs:s}=n,{boxes:r,scores:o}=t,{maxOutputSize:i,iouThreshold:a,scoreThreshold:l}=s;et(r,"NonMaxSuppression");const c=e.data.get(r.dataId).values,u=e.data.get(o.dataId).values,{selectedIndices:h}=uA(c,u,i,a,l);return e.makeTensorInfo([h.length],"int32",new Int32Array(h))}const dA={kernelName:nu,backendName:"cpu",kernelFunc:hA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const fA=Ah;function pA(n){const{inputs:t,backend:e,attrs:s}=n,{boxes:r,scores:o}=t,{maxOutputSize:i,iouThreshold:a,scoreThreshold:l,padToMaxOutputSize:c}=s;et(r,"NonMaxSuppressionPadded");const u=e.data.get(r.dataId).values,h=e.data.get(o.dataId).values,{selectedIndices:d,validOutputs:f}=fA(u,h,i,a,l,c);return[e.makeTensorInfo([d.length],"int32",new Int32Array(d)),e.makeTensorInfo([],"int32",new Int32Array([f]))]}const mA={kernelName:su,backendName:"cpu",kernelFunc:pA};/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const gA=Eh;function bA(n){const{inputs:t,backend:e,attrs:s}=n,{boxes:r,scores:o}=t,{maxOutputSize:i,iouThreshold:a,scoreThreshold:l,softNmsSigma:c}=s;et(r,"NonMaxSuppressionWithScore");const u=e.data.get(r.dataId).values,h=e.data.get(o.dataId).values,d=i,f=a,p=l,g=c,{selectedIndices:m,selectedScores:b}=gA(u,h,d,f,p,g);return[e.makeTensorInfo([m.length],"int32",new Int32Array(m)),e.makeTensorInfo([b.length],"float32",new Float32Array(b))]}const yA={kernelName:ru,backendName:"cpu",kernelFunc:bA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function wA(n){const{inputs:t,backend:e,attrs:s}=n,{indices:r}=t,{dtype:o,depth:i,onValue:a,offValue:l}=s;et(r,"oneHot");const c=Z(r.shape),u=new Float32Array(c*i);u.fill(l);const h=e.data.get(r.dataId).values;for(let d=0;d<c;++d)h[d]>=0&&h[d]<i&&(u[d*i+h[d]]=a);return e.makeTensorInfo([...r.shape,i],o,u)}const kA={kernelName:ba,backendName:"cpu",kernelFunc:wA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function pi(n){const{inputs:t,backend:e}=n,{x:s}=t;if(s.dtype==="string")throw new Error("zerosLike is not supported for string tensors");if(s.dtype==="complex64"){const r=cs({inputs:{input:s},backend:e}),o=pi({inputs:{x:r},backend:e}),i=Bs({inputs:{input:s},backend:e}),a=pi({inputs:{x:i},backend:e}),l=Ie({inputs:{real:o,imag:a},backend:e});return e.disposeIntermediateTensorInfo(r),e.disposeIntermediateTensorInfo(o),e.disposeIntermediateTensorInfo(i),e.disposeIntermediateTensorInfo(a),l}else return mc({backend:e,attrs:{shape:s.shape,value:0,dtype:s.dtype}})}const xA={kernelName:Oa,backendName:"cpu",kernelFunc:pi};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function bm(n){const{inputs:t,backend:e}=n,{x:s}=t;if(s.dtype==="string")throw new Error("onesLike is not supported for string tensors");if(s.dtype==="complex64"){const r=cs({inputs:{input:s},backend:e}),o=bm({inputs:{x:r},backend:e}),i=Bs({inputs:{input:s},backend:e}),a=pi({inputs:{x:i},backend:e}),l=Ie({inputs:{real:o,imag:a},backend:e});return e.disposeIntermediateTensorInfo(r),e.disposeIntermediateTensorInfo(o),e.disposeIntermediateTensorInfo(i),e.disposeIntermediateTensorInfo(a),l}else return mc({backend:e,attrs:{shape:s.shape,value:1,dtype:s.dtype}})}const IA={kernelName:ga,backendName:"cpu",kernelFunc:bm};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function ym(n){const{inputs:t,backend:e,attrs:s}=n,{axis:r}=s;if(t.length===1)return fi({inputs:{input:t[0]},backend:e,attrs:{dim:r}});const o=t[0].shape,i=t[0].dtype;t.forEach(u=>{kc(o,u.shape,"All tensors passed to stack must have matching shapes"),v(i===u.dtype,()=>"All tensors passed to stack must have matching dtypes")});const a=[],l=t.map(u=>{const h=fi({inputs:{input:u},backend:e,attrs:{dim:r}});return a.push(h),h}),c=Ps({inputs:l,backend:e,attrs:{axis:r}});return a.forEach(u=>e.disposeIntermediateTensorInfo(u)),c}const SA={kernelName:ya,backendName:"cpu",kernelFunc:ym};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function vA(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{paddings:o,constantValue:i}=s;et(r,"pad");const a=o.map((y,k)=>y[0]+r.shape[k]+y[1]),l=o.map(y=>y[0]),c=e.data.get(r.dataId).values,u=Z(r.shape),h=r.shape.length,d=it(r.shape),f=Z(a),p=a.length,g=it(a),m=he(r.dtype,f);i!==0&&m.fill(i);for(let y=0;y<u;y++){const w=fs(y,h,d).map((S,T)=>S+l[T]),I=je(w,p,g);m[I]=c[y]}return{dataId:e.write(m,a,r.dtype),shape:a,dtype:r.dtype}}const wm={kernelName:wa,backendName:"cpu",kernelFunc:vA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const NA=Vt((n,t)=>Math.pow(n,t)),$A=Xt(qr,NA),TA={kernelName:qr,backendName:"cpu",kernelFunc:$A};/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function CA(n){const{inputs:t,backend:e,attrs:s}=n,{paramsNestedSplits:r,paramsDenseValues:o,indices:i}=t,{outputRaggedRank:a}=s,l=r.map(b=>e.data.get(b.dataId).values),c=r.map(b=>b.shape),u=e.data.get(o.dataId).values,h=e.data.get(i.dataId).values,[d,f,p]=I2(l,c,u,o.shape,o.dtype,h,i.shape),g=d.map(b=>e.makeTensorInfo([b.length],"int32",b)),m=e.makeTensorInfo(p,o.dtype,f);return g.concat([m])}const AA={kernelName:Qm,backendName:"cpu",kernelFunc:CA};/**
 * @license
 * Copyright 2022 Google LLC.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function EA(n){const{inputs:t,backend:e}=n,{starts:s,limits:r,deltas:o}=t,i=e.data.get(s.dataId).values,a=e.data.get(r.dataId).values,l=e.data.get(o.dataId).values,[c,u]=S2(i,s.shape,s.dtype,a,r.shape,l,o.shape),h=e.makeTensorInfo([c.length],"int32",c),d=e.makeTensorInfo([u.length],s.dtype,u);return[h,d]}const DA={kernelName:tg,backendName:"cpu",kernelFunc:EA};/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function FA(n){const{inputs:t,backend:e,attrs:s}=n,{shape:r,values:o,defaultValue:i,rowPartitionTensors:a}=t,{rowPartitionTypes:l}=s,c=e.data.get(r.dataId).values,u=e.data.get(o.dataId).values,h=e.data.get(i.dataId).values,d=a.map(m=>e.data.get(m.dataId).values),f=a.map(m=>m.shape),[p,g]=v2(c,r.shape,u,o.shape,o.dtype,h,i.shape,d,f,l);return e.makeTensorInfo(p,o.dtype,g)}const MA={kernelName:eg,backendName:"cpu",kernelFunc:FA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function RA(n){const{backend:t,attrs:e}=n,{start:s,stop:r,dtype:o,step:i}=e,a=N2(s,r,i,o);return t.makeTensorInfo([a.length],o,a)}const zA={kernelName:iu,backendName:"cpu",kernelFunc:RA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const LA=It(xa,n=>1/n),OA={kernelName:xa,backendName:"cpu",kernelFunc:LA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function _A(n){const{inputs:t,backend:e,attrs:s}=n,{images:r}=t,{alignCorners:o,halfPixelCenters:i,size:a}=s;et(r,"resizeBilinear");const l=it(r.shape),[c,u]=a,[h,d,f,p]=r.shape,g=e.data.get(r.dataId).values,m=new Float32Array(Z([h,c,u,p])),b=[o&&c>1?d-1:d,o&&u>1?f-1:f],y=[o&&c>1?c-1:c,o&&u>1?u-1:u];let k=0;const w=b[0]/y[0],I=b[1]/y[1];for(let S=0;S<h;S++)for(let T=0;T<c;T++){let C;i?C=w*(T+.5)-.5:C=w*T;const N=Math.max(0,Math.floor(C)),$=C-N,x=Math.min(d-1,Math.ceil(C)),F=S*l[0]+N*l[1],M=S*l[0]+x*l[1];for(let O=0;O<u;O++){let L;i?L=I*(O+.5)-.5:L=I*O;const B=Math.max(0,Math.floor(L)),G=L-B,W=Math.min(f-1,Math.ceil(L)),V=F+B*l[2],U=M+B*l[2],q=F+W*l[2],K=M+W*l[2];for(let j=0;j<p;j++){const Y=g[V+j],J=g[U+j],tt=g[q+j],nt=g[K+j],at=Y+(tt-Y)*G,ot=J+(nt-J)*G,ht=at+(ot-at)*$;m[k++]=ht}}}return e.makeTensorInfo([h,c,u,p],"float32",m)}const BA={kernelName:va,backendName:"cpu",kernelFunc:_A};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function PA(n){const{inputs:t,backend:e,attrs:s}=n,{images:r,dy:o}=t,{alignCorners:i}=s;et([o,r],"resizeBilinearGrad");const a=it(r.shape),[l,c,u,h]=r.shape,[,d,f]=o.shape,p=new Float32Array(l*c*u*h),g=[i&&d>1?c-1:c,i&&f>1?u-1:u],m=[i&&d>1?d-1:d,i&&f>1?f-1:f],b=g[0]/m[0],y=g[1]/m[1],k=e.data.get(o.dataId).values;let w=0;for(let I=0;I<l;I++){const S=I*a[0];for(let T=0;T<d;T++){const C=T*b,N=Math.floor(C),$=Math.min(Math.ceil(C),c-1),x=S+N*a[1],F=S+$*a[1],M=C-N,O=1-M;for(let L=0;L<f;L++){const B=L*y,G=Math.floor(B),W=Math.min(Math.ceil(B),u-1),V=B-G,U=1-V,q=x+G*a[2],K=x+W*a[2],j=F+G*a[2],Y=F+W*a[2],J=O*U,tt=O*V,nt=M*U,at=M*V;for(let ot=0;ot<h;ot++){const ht=k[w++];p[q+ot]+=ht*J,p[K+ot]+=ht*tt,p[j+ot]+=ht*nt,p[Y+ot]+=ht*at}}}}return e.makeTensorInfo([l,u,c,h],"float32",p)}const WA={kernelName:cu,backendName:"cpu",kernelFunc:PA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function VA(n){const{inputs:t,backend:e,attrs:s}=n,{images:r}=t,{alignCorners:o,halfPixelCenters:i,size:a}=s;et(r,"resizeNearestNeighbor");const l=it(r.shape),[c,u]=a,[h,d,f,p]=r.shape,g=e.data.get(r.dataId).values,m=new Float32Array(h*c*u*p),b=[o&&c>1?d-1:d,o&&u>1?f-1:f],y=[o&&c>1?c-1:c,o&&u>1?u-1:u],k=b[0]/y[0],w=b[1]/y[1];let I=0;for(let S=0;S<h;S++){const T=S*l[0];for(let C=0;C<c;C++){const N=i?k*(C+.5):k*C;let $=Math.min(d-1,o?Math.round(N):Math.floor(N));i&&($=Math.max(0,$));const x=T+$*l[1];for(let F=0;F<u;F++){const M=i?w*(F+.5):w*F;let O=Math.min(f-1,o?Math.round(M):Math.floor(M));i&&(O=Math.max(0,O));const L=x+O*l[2];for(let B=0;B<p;B++){const G=g[L+B];m[I++]=G}}}}return e.makeTensorInfo([h,c,u,p],r.dtype,m)}const GA={kernelName:Sa,backendName:"cpu",kernelFunc:VA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function UA(n){const{inputs:t,backend:e,attrs:s}=n,{images:r,dy:o}=t,{alignCorners:i}=s;et([o,r],"resizeNearestNeighborGrad");const a=it(r.shape),l=it(o.shape),[c,u,h,d]=r.shape,[,f,p]=o.shape,g=new Float32Array(c*u*h*d),m=e.data.get(o.dataId).values,b=[i&&f>1?u-1:u,i&&p>1?h-1:h],y=[i&&f>1?f-1:f,i&&p>1?p-1:p],k=b[0]/y[0],w=b[1]/y[1],I=1/k,S=1/w,T=Math.ceil(I)*2+2,C=Math.ceil(S)*2+2;for(let N=0;N<c;N++){const $=N*a[0];for(let x=0;x<u;x++){const F=$+x*a[1],M=Math.floor(x*I),O=Math.floor(M-T/2);for(let L=0;L<h;L++){const B=F+L*a[2],G=Math.floor(L*S),W=Math.floor(G-C/2);for(let V=0;V<d;V++){let U=0;for(let q=0;q<T;q++){const K=q+O;if(K<0||K>=f)continue;const j=$+K*l[1],Y=K*k,J=Math.min(u-1,i?Math.round(Y):Math.floor(Y));if(x===J)for(let tt=0;tt<C;tt++){const nt=tt+W;if(nt<0||nt>=p)continue;const at=j+nt*l[2],ot=nt*w,ht=Math.min(h-1,i?Math.round(ot):Math.floor(ot));L===ht&&(U+=m[at+V])}}g[B+V]=U}}}}return e.makeTensorInfo(r.shape,r.dtype,g)}const HA={kernelName:lu,backendName:"cpu",kernelFunc:UA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function qA(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{dims:o}=s;et(r,"reverse");const i=r.shape.length,a=Ft(o,r.shape);if(i===0)return hn({inputs:{x:r},backend:e});const l=new te(r.shape,r.dtype),c=e.bufferSync(r);for(let u=0;u<l.size;u++){const h=l.indexToLoc(u),d=h.slice();a.forEach(f=>d[f]=r.shape[f]-1-d[f]),l.set(c.get(...d),...h)}return e.makeTensorInfo(l.shape,l.dtype,l.values)}const jA={kernelName:Na,backendName:"cpu",kernelFunc:qA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const KA={kernelName:fu,backendName:"cpu",kernelFunc:({inputs:n,attrs:t,backend:e})=>{const{image:s}=n,{radians:r,fillValue:o,center:i}=t,a=e,l=he(s.dtype,Z(s.shape)),[c,u,h,d]=s.shape,[f,p]=wk(i,u,h),g=255,m=Math.sin(r),b=Math.cos(r),y=a.data.get(s.dataId).values;for(let w=0;w<c;w++){const I=w*h*u*d;for(let S=0;S<u;S++){const T=S*(h*d);for(let C=0;C<h;C++){const N=C*d;for(let $=0;$<d;$++){const x=[c,S,C,$],F=x[2],M=x[1];let O=(F-f)*b-(M-p)*m,L=(F-f)*m+(M-p)*b;O=Math.round(O+f),L=Math.round(L+p);let B=o;if(typeof o!="number"&&($===3?B=g:B=o[$]),O>=0&&O<h&&L>=0&&L<u){const W=L*(h*d),V=O*d,U=I+W+V+$;B=y[U]}const G=I+T+N+$;l[G]=B}}}}return{dataId:a.write(l,s.shape,s.dtype),shape:s.shape,dtype:s.dtype}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const XA=It(Xr,n=>{const t=Math.floor(n);return n-t<.5?Math.floor(n):n-t>.5?Math.ceil(n):t%2===0?t:t+1}),ZA={kernelName:Xr,backendName:"cpu",kernelFunc:XA};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function JA(n){const{inputs:t,backend:e,attrs:s}=n,{indices:r,updates:o}=t,{shape:i}=s,{sliceRank:a,numUpdates:l,sliceSize:c,strides:u,outputSize:h}=yl(o,r,i),d=!0,f=e.bufferSync(r),p=e.bufferSync(o),g=_s(f,p,i,h,c,l,a,u,0,d);return e.makeTensorInfo(i,g.dtype,g.values)}const YA={kernelName:ng,backendName:"cpu",kernelFunc:JA};/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function QA(n,t){let e=0,s=n.length,r=0;for(;e<s;)r=Math.floor((e+s)/2),n[r]<t?e=r+1:s=r;return s}function tE(n,t){let e=0,s=n.length,r=0;for(;e<s;)r=Math.floor((e+s)/2),n[r]<=t?e=r+1:s=r;return s}function eE(n,t,e,s,r,o){const i=Gt("int32",e*r);for(let a=0;a<e;++a){const l=n.slice(a*s,(a+1)*s),c=a*r;for(let u=0;u<r;++u)i[c+u]=o==="left"?QA(l,t[u+c]):tE(l,t[u+c])}return i}/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function nE(n){const{inputs:t,backend:e,attrs:s}=n,{sortedSequence:r,values:o}=t,{side:i}=s,a=e.data.get(r.dataId).values,l=e.data.get(o.dataId).values,c=eE(a,l,r.shape[0],r.shape[1],o.shape[1],i);return e.makeTensorInfo(o.shape,"int32",c)}const sE={kernelName:rg,backendName:"cpu",kernelFunc:nE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function rE(n){const{inputs:t,backend:e}=n,{condition:s,t:r,e:o}=t;et([s,r,o],"select");const i=s.shape.length,a=e.data.get(s.dataId).values,l=e.data.get(r.dataId).values,c=e.data.get(o.dataId).values,u=ms(r.dtype,o.dtype),h=ie(Z(r.shape),u);let d=0;const f=i===0||i>1||r.shape.length===1?1:Z(r.shape.slice(1));for(let p=0;p<a.length;p++)for(let g=0;g<f;g++)a[p]===1?h[d++]=l[p]:h[d++]=c[p];return e.makeTensorInfo(r.shape,u,h)}const oE={kernelName:$a,backendName:"cpu",kernelFunc:rE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const iE=Kh,aE=Xh,lE=It(Jr,n=>n>=0?aE*n:iE*(Math.exp(n)-1)),cE={kernelName:Jr,backendName:"cpu",kernelFunc:lE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const uE=It(Ca,n=>n<0?-1:n>0?1:0),hE={kernelName:Ca,backendName:"cpu",kernelFunc:uE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const dE=It(Yr,n=>Math.sin(n)),fE={kernelName:Yr,backendName:"cpu",kernelFunc:dE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const pE=It(Qr,n=>Math.sinh(n)),mE={kernelName:Qr,backendName:"cpu",kernelFunc:pE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const km=Math.log(11920928955078125e-23)+2,gE=It(eo,n=>{const t=n>-km,e=n<km,s=Math.exp(n);let r;return e?r=s:t?r=n:r=Math.log(1+s),r}),bE={kernelName:eo,backendName:"cpu",kernelFunc:gE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function yE(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{blockShape:o,paddings:i}=s;et([r],"spaceToBatchND");const a=Z(o),l=[[0,0]];l.push(...i);for(let S=1+o.length;S<r.shape.length;++S)l.push([0,0]);const c=wm.kernelFunc({inputs:{x:r},backend:e,attrs:{paddings:l,constantValue:0}}),u=Hh(c.shape,o,a,!1),h=qh(u.length,o.length,!1),d=jh(c.shape,o,a,!1),g=At({inputs:{x:c},backend:e,attrs:{shape:u}}),y=me({inputs:{x:g},backend:e,attrs:{perm:h}}),I=At({inputs:{x:y},backend:e,attrs:{shape:d}});return e.disposeIntermediateTensorInfo(c),e.disposeIntermediateTensorInfo(g),e.disposeIntermediateTensorInfo(y),I}const wE={kernelName:Ea,backendName:"cpu",kernelFunc:yE};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function kE(n){const{inputs:t,backend:e}=n,{indices:s,values:r,denseShape:o,defaultValue:i}=t;if(o.shape.length!==1)throw new Error(`Dense shape must be a vector, saw:
        ${o.shape}`);if(s.shape.length!==2)throw new Error(`Indices must be a matrix, saw:
        ${s.shape}`);if(r.shape.length!==1)throw new Error(`Values must be a vector, saw:
        ${r.shape}`);if(i.shape.length!==0)throw new Error(`Default value must be a scalar, saw:
        ${i.shape}`);const a=e.data.get(s.dataId).values,l=e.data.get(r.dataId).values,c=e.data.get(o.dataId).values,u=e.data.get(i.dataId).values[0],[h,d,f,p,g]=F2(a,s.shape,s.dtype,l,r.dtype,c,u);return[e.makeTensorInfo(d,s.dtype,h),e.makeTensorInfo([d[0]],r.dtype,f),e.makeTensorInfo([p.length],"bool",new Uint8Array(p.map(m=>Number(m)))),e.makeTensorInfo([g.length],s.dtype,new Int32Array(g))]}const xE={kernelName:og,backendName:"cpu",kernelFunc:kE};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function IE(n){const{inputs:t,backend:e}=n,{inputIndices:s,inputShape:r,newShape:o}=t;if(s.shape.length!==2)throw new Error(`Input indices should be a matrix but received shape
        ${s.shape}`);if(r.shape.length!==1)throw new Error(`Input shape should be a vector but received shape
        ${r.shape}`);if(o.shape.length!==1)throw new Error(`Target shape should be a vector but received shape ${o.shape}`);const i=Array.from(e.data.get(r.dataId).values),a=e.data.get(s.dataId).values,l=Array.from(e.data.get(o.dataId).values),[c,u,h]=M2(a,s.shape,s.dtype,i,l);return[e.makeTensorInfo(u,s.dtype,c),e.makeTensorInfo([h.length],o.dtype,new Int32Array(h))]}const SE={kernelName:ig,backendName:"cpu",kernelFunc:IE};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function vE(n){const{inputs:t,backend:e}=n,{data:s,indices:r,segmentIds:o}=t;if(s.shape.length<1)throw new Error("Data should be at least 1 dimensional but received scalar");if(r.shape.length!==1)throw new Error(`Indices should be a vector but received shape
          ${r.shape}`);if(o.shape.length!==1)throw new Error(`Segment ids should be a vector but received shape
          ${o.shape}`);if(r.shape[0]!==o.shape[0])throw new Error("segmentIds and indices should have same size.");const i=e.data.get(s.dataId).values,a=e.data.get(r.dataId).values,l=e.data.get(o.dataId).values,[c,u]=nm(i,s.shape,s.dtype,a,l,!0);return e.makeTensorInfo(u,s.dtype,c)}const NE={kernelName:ag,backendName:"cpu",kernelFunc:vE};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function $E(n){const{inputs:t,backend:e}=n,{data:s,indices:r,segmentIds:o}=t;if(s.shape.length<1)throw new Error("Data should be at least 1 dimensional but received scalar");if(r.shape.length!==1)throw new Error(`Indices should be a vector but received shape
         ${r.shape}`);if(o.shape.length!==1)throw new Error(`Segment ids should be a vector but received shape
         ${o.shape}`);if(r.shape[0]!==o.shape[0])throw new Error("segmentIds and indices should have same size.");const i=e.data.get(s.dataId).values,a=e.data.get(r.dataId).values,l=e.data.get(o.dataId).values,[c,u]=nm(i,s.shape,s.dtype,a,l);return e.makeTensorInfo(u,s.dtype,c)}const TE={kernelName:lg,backendName:"cpu",kernelFunc:$E};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function CE(n){const{inputs:t,backend:e,attrs:s}=n,{sparseIndices:r,sparseValues:o,defaultValue:i}=t,{outputShape:a}=s,{sliceRank:l,numUpdates:c,sliceSize:u,strides:h,outputSize:d}=yl(o,r,a),f=!1,p=e.bufferSync(r);let g;switch(o.dtype){case"bool":{const m=e.bufferSync(o),b=!!e.data.get(i.dataId).values[0];g=_s(p,m,a,d,u,c,l,h,b,f);break}case"float32":{const m=e.bufferSync(o),b=e.data.get(i.dataId).values[0];g=_s(p,m,a,d,u,c,l,h,b,f);break}case"int32":{const m=e.bufferSync(o),b=e.data.get(i.dataId).values[0];g=_s(p,m,a,d,u,c,l,h,b,f);break}case"string":{const m=e.bufferSync(o),b=Us(e.data.get(i.dataId).values[0]);g=_s(p,m,a,d,u,c,l,h,b,f);break}default:throw new Error(`Unsupported type ${o.dtype}`)}return e.makeTensorInfo(a,g.dtype,g.values)}const AE={kernelName:cg,backendName:"cpu",kernelFunc:CE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function EE(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{numOrSizeSplits:o,axis:i}=s,a=Ft(i,r.shape)[0],l=Wk(r,o,a),c=new Array(r.shape.length).fill(0),u=r.shape.slice();return l.map(h=>{const d=[...u];d[a]=h;const f=us({inputs:{x:r},backend:e,attrs:{begin:c,size:d}});return c[a]+=h,f})}const DE={kernelName:Da,backendName:"cpu",kernelFunc:EE};/**
 * @license
 * Copyright 2019 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const FE={kernelName:uu,backendName:"cpu",kernelFunc:({inputs:n,backend:t})=>{const{x:e}=n,s=t;et(e,"square");const r=s.data.get(e.dataId).values,o=new Float32Array(r.length);for(let a=0;a<r.length;++a){const l=r[a];o[a]=l*l}return{dataId:s.write(o,e.shape,e.dtype),shape:e.shape,dtype:e.dtype}}};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const ME=It(io,(n,t)=>{const e=t;return isNaN(n)?NaN:n>0?1:e.alpha}),RE={kernelName:io,backendName:"cpu",kernelFunc:ME};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function zE(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{begin:o,end:i,strides:a,beginMask:l,endMask:c,ellipsisMask:u,newAxisMask:h,shrinkAxisMask:d}=s;et(r,"stridedSlice");const{finalShapeSparse:f,finalShape:p,isIdentity:g,sliceDim0:m,isSimpleSlice:b,begin:y,end:k,strides:w}=ck(r.shape,o,i,a,l,c,u,h,d);let I;if(g)I=At({inputs:{x:r},backend:e,attrs:{shape:p}});else if(m||b){v(r.shape.length>=1,()=>`Input must have rank at least 1, got: ${r.shape.length}`);const S=ik(y,k,w),T=us({inputs:{x:r},backend:e,attrs:{begin:y,size:S}});I=At({inputs:{x:T},backend:e,attrs:{shape:p}}),e.disposeIntermediateTensorInfo(T)}else{const S=e.bufferSync(r),T=V2(f,S,w,y);I=e.makeTensorInfo(p,T.dtype,T.values)}return I}const LE={kernelName:ug,backendName:"cpu",kernelFunc:zE};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function OE(n){const{inputs:t,backend:e,attrs:s}=n,{separator:r,nGramWidths:o,leftPad:i,rightPad:a,padWidth:l,preserveShortSequences:c}=s,{data:u,dataSplits:h}=t,d=e.data.get(u.dataId).values,f=e.data.get(h.dataId).values,[p,g]=U2(d,f,r,o,i,a,l,c);return[e.makeTensorInfo([p.length],"string",p),e.makeTensorInfo(h.shape,"int32",g)]}const _E={kernelName:hg,backendName:"cpu",kernelFunc:OE};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function BE(n){const{inputs:t,backend:e,attrs:s}=n,{skipEmpty:r}=s,{input:o,delimiter:i}=t;if(o.dtype!=="string")throw new Error("Input must be of datatype string");if(o.shape.length!==1)throw new Error(`Input must be a vector, got shape: ${o.shape}`);if(i.shape.length!==0)throw new Error(`Delimiter must be a scalar, got shape: ${i.shape}`);const a=e.data.get(o.dataId).values,l=e.data.get(i.dataId).values[0],[c,u,h]=q2(a,l,r),d=u.length;return[e.makeTensorInfo([d,2],"int32",c),e.makeTensorInfo([d],"string",u),e.makeTensorInfo([2],"int32",new Int32Array(h))]}const PE={kernelName:dg,backendName:"cpu",kernelFunc:BE};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function WE(n){const{inputs:t,backend:e,attrs:s}=n,{numBuckets:r}=s,{input:o}=t;if(o.dtype!=="string")throw new Error("Input must be of datatype string");if(r<=0)throw new Error("Number of buckets must be at least 1");const i=e.data.get(o.dataId).values,a=j2(i,r);return e.makeTensorInfo(o.shape,"int32",a)}const VE={kernelName:fg,backendName:"cpu",kernelFunc:WE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const GE=It(Ra,n=>Math.tan(n)),UE={kernelName:Ra,backendName:"cpu",kernelFunc:GE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const HE=It(ro,n=>Math.tanh(n)),qE={kernelName:ro,backendName:"cpu",kernelFunc:HE};/**
 * @license
 * Copyright 2022 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function jE(n){const{inputs:t,backend:e}=n,{tensor:s,indices:r,updates:o}=t,{sliceRank:i,numUpdates:a,sliceSize:l,strides:c,outputSize:u}=yl(o,r,s.shape),h=!1,d=e.bufferSync(r),f=e.bufferSync(o),p=e.bufferSync(s),g=_s(d,f,s.shape,u,l,a,i,c,p,h);return e.makeTensorInfo(s.shape,g.dtype,g.values)}const KE={kernelName:sg,backendName:"cpu",kernelFunc:jE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function XE(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{reps:o}=s;et(r,"tile");const i=J2(e.bufferSync(r),o);return e.makeTensorInfo(i.shape,i.dtype,i.values)}const ZE={kernelName:oo,backendName:"cpu",kernelFunc:XE};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function JE(n){const{inputs:t,backend:e,attrs:s}=n,{x:r}=t,{k:o,sorted:i}=s;et(r,"topk");const a=e.data.get(r.dataId).values,[l,c]=Y2(a,r.shape,r.dtype,o,i);return[e.makeTensorInfo(l.shape,l.dtype,l.values),e.makeTensorInfo(c.shape,c.dtype,c.values)]}const YE={kernelName:pg,backendName:"cpu",kernelFunc:JE};/**
 * @license
 * Copyright 2021 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function QE(n){const{inputs:t,attrs:e,backend:s}=n,{image:r,transforms:o}=t,{interpolation:i,fillMode:a,fillValue:l,outputShape:c}=e,[u,h,d,f]=r.shape,[p,g]=c??[h,d],m=[u,p,g,f],b=it(r.shape),y=b[0],k=b[1],w=b[2],I=it(m),S=I[0],T=I[1],C=I[2],N=he(r.dtype,Z(m));N.fill(l);const $=s.data.get(r.dataId).values,x=s.data.get(o.dataId).values;for(let M=0;M<u;++M){const O=o.shape[0]===1?x:x.subarray(M*8,M*8+8);for(let L=0;L<p;++L)for(let B=0;B<g;++B)for(let G=0;G<f;++G){let W;const V=O[6]*B+O[7]*L+1;if(V===0)continue;const U=(O[0]*B+O[1]*L+O[2])/V,q=(O[3]*B+O[4]*L+O[5])/V,K=xm(U,d,a),j=xm(q,h,a);switch(i){case"nearest":W=oD($,h,d,y,k,w,M,j,K,G,l);break;case"bilinear":W=iD($,h,d,y,k,w,M,j,K,G,l);break;default:throw new Error(`Error in Transform: Expect 'nearest' or 'bilinear', but got ${i}`)}const Y=M*S+L*T+B*C+G;N[Y]=W}return s.makeTensorInfo(m,r.dtype,N)}return{dataId:s.write(N,m,r.dtype),shape:r.shape,dtype:r.dtype}}const tD={kernelName:du,backendName:"cpu",kernelFunc:QE};function xm(n,t,e){switch(e){case"reflect":return eD(n,t);case"wrap":return nD(n,t);case"nearest":return rD(n,t);case"constant":default:return sD(n)}}function eD(n,t){let e=n;if(e<0)if(t<=1)e=0;else{const s=2*t;e<s&&(e=s*Math.trunc(-e/s)+e),e=e<-t?e+s:-e-1}else if(e>t-1)if(t<=1)e=0;else{const s=2*t;e-=s*Math.trunc(e/s),e>=t&&(e=s-e-1)}return bi(0,e,t-1)}function nD(n,t){let e=n;if(e<0)if(t<=1)e=0;else{const s=t-1;e+=t*(Math.trunc(-e/s)+1)}else if(e>t-1)if(t<=1)e=0;else{const s=t-1;e-=t*Math.trunc(e/s)}return bi(0,e,t-1)}function sD(n,t){return n}function rD(n,t){return bi(0,n,t-1)}function vr(n,t,e,s,r,o,i,a,l,c,u){const h=i*s+a*r+l*o+c;return 0<=a&&a<t&&0<=l&&l<e?n[h]:u}function oD(n,t,e,s,r,o,i,a,l,c,u){const h=Math.round(a),d=Math.round(l);return vr(n,t,e,s,r,o,i,h,d,c,u)}function iD(n,t,e,s,r,o,i,a,l,c,u){const h=Math.floor(a),d=Math.floor(l),f=h+1,p=d+1,g=(p-l)*vr(n,t,e,s,r,o,i,h,d,c,u)+(l-d)*vr(n,t,e,s,r,o,i,h,p,c,u),m=(p-l)*vr(n,t,e,s,r,o,i,f,d,c,u)+(l-d)*vr(n,t,e,s,r,o,i,f,p,c,u);return(f-a)*g+(a-h)*m}/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the License);
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an AS IS BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function aD(n){const{inputs:t,attrs:e,backend:s}=n,{axis:r}=e,{x:o}=t;et(o,"unique");const i=s.data.get(o.dataId).values,{outputValues:a,outputShape:l,indices:c}=Q2(i,r,o.shape,o.dtype);return[s.makeTensorInfo(l,o.dtype,a),s.makeTensorInfo([c.length],"int32",c)]}const lD={kernelName:mg,backendName:"cpu",kernelFunc:aD};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function cD(n){const{inputs:t,backend:e,attrs:s}=n,{value:r}=t;let{axis:o}=s;o<0&&(o+=r.shape.length);const i=r.shape.length,a=r.shape[o],l=new Array(i-1);let c=0;for(let f=0;f<i;f++)f!==o&&(l[c++]=r.shape[f]);const u=new Array(i).fill(0),h=r.shape.slice();h[o]=1;const d=new Array(a);for(let f=0;f<d.length;f++){u[o]=f;const p=us({inputs:{x:r},backend:e,attrs:{begin:u,size:h}});d[f]=At({inputs:{x:p},backend:e,attrs:{shape:l}}),e.disposeIntermediateTensorInfo(p)}return d}const uD={kernelName:za,backendName:"cpu",kernelFunc:cD};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */function hD(n){const{inputs:t,backend:e,attrs:s}=n,{x:r,segmentIds:o}=t,{numSegments:i}=s;et(r,"unsortedSegmentSum");const a=r.shape.length,l=o.shape.length,c=[],u=[],h=a-l;let d=o;for(let p=0;p<h;++p){const g=fi({inputs:{input:d},backend:e,attrs:{dim:p+1}});d=g,u.push(g)}for(let p=0;p<i;++p){const g=Ga(p,"int32"),m=e.makeTensorInfo([],"int32",g),b=jp({inputs:{a:m,b:d},backend:e}),y=Bn({inputs:{x:b},backend:e,attrs:{dtype:"float32"}}),k=ui({inputs:{a:y,b:r},backend:e}),w=Sr({inputs:{x:k},backend:e,attrs:{axis:0,keepDims:!1}});c.push(w),u.push(m),u.push(b),u.push(y),u.push(k),u.push(w)}const f=ym({inputs:c,backend:e,attrs:{axis:0}});return u.forEach(p=>e.disposeIntermediateTensorInfo(p)),f}const dD={kernelName:La,backendName:"cpu",kernelFunc:hD};/**
 * @license
 * Copyright 2020 Google LLC. All Rights Reserved.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * =============================================================================
 */const fD=[c$,sN,h$,f$,hN,m$,b$,w$,x$,S$,N$,T$,A$,F$,R$,O$,B$,W$,G$,a$,H$,j$,X$,mN,J$,lN,yN,Q$,rN,tT,nT,sT,oT,aT,cT,hT,fT,mT,bT,wT,xT,ST,NT,TT,CT,ET,FT,RT,zT,LT,OT,BT,VT,t$,UT,xN,YT,SN,QT,$N,oC,iC,lC,AN,FN,uC,dC,pC,gC,ON,PN,oN,yC,eT,kC,IC,vC,e$,GN,qN,$C,ZN,CC,DC,MC,LC,_C,PC,WC,t2,GC,HC,jC,XC,JC,QC,eA,s2,sA,iA,cA,o2,l2,dA,mA,yA,h2,kA,IA,SA,wm,TA,s$,m2,AA,DA,MA,zA,iN,fc,OA,r$,o$,i$,BA,WA,GA,HA,jA,KA,ZA,C2,YA,sE,oE,cE,A2,hE,fE,mE,D2,aA,bE,wE,xE,SE,NE,TE,AE,DE,z2,FE,_2,W2,RE,LE,_E,PE,VE,Z2,PT,UE,qE,KE,ZE,YE,tD,d2,lD,uD,dD,xA];for(const n of fD)bg(n);function pD(n){return n.toLowerCase().replace(/\bkey [a-z][a-z0-9_-]*/g,"key slotkey").replace(/\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b/g," slotuser ").replace(/\b[a-z][a-z0-9]*-\d+\b/g," slotkey ").replace(/"[^"]*"/g," slottext ").replace(/\b\d{4}-\d{2}-\d{2}\b/g," slotdate ").replace(/\b\d+\b/g," slotnumber ").match(/[a-z]+/g)||[]}let wn,mi,gc;async function mD(){if(await qg("cpu"),await jg(),mi=await zv("/models/operator/model.json"),wn=mi.getUserDefinedMetadata(),wn.version!==3||wn.trainingExamples<100)throw mi.dispose(),new Error("Model version mismatch")}self.onmessage=async n=>{const{id:t,clauses:e}=n.data;try{gc||(gc=mD()),await gc;const s=e.map(r=>z(()=>{const o=new Set(pD(r)),i=wn.vocabulary.map(u=>o.has(u)?1:0),a=mi.predict(Oo([i])).dataSync(),l=Array.from(a).map((u,h)=>({confidence:u,intent:wn.intents[h]})).sort((u,h)=>h.confidence-u.confidence),c=[...o].filter(u=>wn.vocabulary.includes(u)).length/Math.max(o.size,1);return{...l[0],accepted:l[0].intent!=="fallback"&&l[0].confidence>=wn.threshold&&l[0].confidence-l[1].confidence>=wn.margin&&c>=.9}}));self.postMessage({id:t,predictions:s,trainingExamples:wn.trainingExamples})}catch{gc=void 0,self.postMessage({id:t,error:"Local model unavailable. Choose cloud planning to continue."})}}})();
