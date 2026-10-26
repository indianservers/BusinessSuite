import isEmail from 'validator/lib/isEmail';
import contract from './contract.json';
export { contract };
export const PHONE_ERROR=contract.phone_error;
export const NATIONAL_PHONE_LENGTH=contract.national_phone_length;
export function passoutYears(today:string) {
  return Array.from({length:Math.max(0,Number(today.slice(0,4))-1970+1)},(_,index)=>String(1970+index));
}
export const phoneFields=new Set(['mobile','mobile_number','phone','phone_number','alternate_phone','whatsapp_number','emergency_contact','emergency_contact_number','contact_phone','contact_number','business_phone_number','primary_phone','secondary_phone']);
export function phoneError(number:unknown,code:unknown,required=false) {
  if(!required&&(number===''||number==null))return '';
  if(typeof number!=='string'||number.length!==NATIONAL_PHONE_LENGTH||!/^[0-9]+$/.test(number))return PHONE_ERROR;
  if(typeof code!=='string'||!contract.countries.some(country=>country.code===code))return 'Select a supported country calling code.';
  return '';
}
export function emailError(value:unknown,required=false) {
  if(!required&&(value===''||value==null))return '';
  const domain=typeof value==='string'?value.slice(value.lastIndexOf('@')+1).toLowerCase():'';
  if(contract.reserved_email_domains.some(reserved=>domain===reserved||domain.endsWith('.'+reserved)))return 'Enter a valid email address without spaces.';
  return typeof value==='string'&&!/\s/.test(value)&&value.length<=254&&isEmail(value,{allow_utf8_local_part:true,require_tld:true})?'':'Enter a valid email address without spaces.';
}
export function textError(value:unknown,max:number,required=true,multiline=false) {
  if(!required&&(value===''||value==null))return '';
  if(typeof value!=='string'||!value.trim()||!/[^\p{C}\p{Z}]/u.test(value.trim()))return 'This field is required.';
  if(value.trim().length>max)return `Use ${max} characters or fewer.`;
  const checked=multiline?value.replace(/[\n\r\t]/g,''):value;
  if(/[\p{Cc}\p{Cs}]/u.test(checked))return 'Remove control characters from this field.';
  return '';
}
export function identityError(kind:string,value:string) {
  if(!value||value!==value.trim())return 'Enter the ID number without surrounding spaces.';
  if(kind==='Aadhaar')return /^[0-9]{12}$/.test(value)?'':'Enter the 12-digit Aadhaar number. Format checking does not verify identity.';
  if(kind==='PAN')return /^[A-Z]{5}[0-9]{4}[A-Z]$/.test(value)?'':'Enter a PAN using five uppercase letters, four digits and one uppercase letter.';
  // Passport and legacy EPIC formats vary. Do not impose an unverified Indian-only pattern.
  return textError(value,40)||(value.length<4?'Use at least 4 characters as printed on the document.':'');
}
export function applicationErrors(form:Record<string,string>,roles:string[],today:string) {
  const errors:Record<string,string>={};
  const set=(key:string,value:string)=>{if(value)errors[key]=value;};
  for(const [key,max] of Object.entries({full_name:160,parent_name:160,city:100,college:200,specialization:150,skills:1000,address:200}))set(key,textError(form[key],max,true,key==='address'));
  if(form.college.trim().length<2)errors.college='Use at least 2 characters.';
  if(form.address.trim().length<5)errors.address='Use at least 5 characters.';
  if(!/^[1-9][0-9]{5}$/.test(form.pincode || ''))errors.pincode='Enter a valid 6-digit PIN code.';
  set('email',emailError(form.email,true));
  set('mobile',phoneError(form.mobile,form.mobile_country_code,true));
  set('emergency_contact',phoneError(form.emergency_contact,form.emergency_contact_country_code,true));
  set('identity_number',identityError(form.identity_type,form.identity_number));
  const choices:Record<string,string[]>={identity_type:contract.identity_types,gender:['Male','Female','Other'],state:contract.states,degree:contract.degrees,current_year:contract.current_years,area_of_interest:contract.areas,mode:contract.modes,duration:contract.durations,employment_type:['Intern','Full-time','Part-time','Contract'],role:roles};
  for(const [key,values] of Object.entries(choices))if(!values.includes(form[key]))errors[key]='Select a supported option.';
  for(const key of ['tenth_marks','twelfth_marks']) {
    if(key==='twelfth_marks'&&form[key]==='')continue;
    if(!/^(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)$/.test(form[key])||!Number.isFinite(Number(form[key]))||Number(form[key])<0||Number(form[key])>100)errors[key]='Enter a percentage from 0 to 100.';
  }
  const validDate=(value:string)=>/^\d{4}-\d{2}-\d{2}$/.test(value)&&!Number.isNaN(Date.parse(value))&&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value;
  if(!validDate(form.date_of_birth)||form.date_of_birth>=today)errors.date_of_birth='Enter a real date of birth in the past.';
  if(!validDate(form.available_from)||form.available_from<today)errors.available_from='Availability must be today or later.';
  if(!passoutYears(today).includes(form.passout_year))errors.passout_year=`Select a pass-out year from 1970 to ${today.slice(0,4)}.`;
  for(const key of ['linkedin','portfolio','github'])if(form[key]){try{const u=new URL(form[key]);if(!['http:','https:'].includes(u.protocol)||/\s/.test(form[key]))throw Error();}catch{errors[key]='Enter a complete HTTP or HTTPS URL.';}}
  const skills=form.skills.split(',').map(value=>value.trim());
  if(skills.length>30||skills.some(value=>!value||value.length>80))errors.skills='Enter up to 30 comma-separated skills, each 1–80 characters.';
  return errors;
}
