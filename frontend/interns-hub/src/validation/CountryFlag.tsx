// Local SVG assets render reliably on Windows too; no third-party image calls.
const flags=import.meta.glob('/node_modules/country-flag-icons/3x2/*.svg',{eager:true,query:'?url',import:'default'}) as Record<string,string>;
export function CountryFlag({iso}:{iso:string}){
  const source=flags['/node_modules/country-flag-icons/3x2/'+iso+'.svg'];
  return source?<img src={source} alt="" aria-hidden="true" loading="lazy" style={{display:'inline-block',width:18,height:12,objectFit:'cover',verticalAlign:'middle',flexShrink:0}}/>:<span aria-hidden="true">{iso}</span>;
}
