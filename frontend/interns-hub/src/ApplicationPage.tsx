import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  UserRound,
  Users,
  Phone,
  Mail,
  CreditCard,
  Hash,
  CalendarDays,
  MapPin,
  GraduationCap,
  School,
  Layers,
  Target,
  Settings,
  Briefcase,
  Monitor,
  Clock,
  Home,
  Linkedin,
  ArrowRight,
  ArrowLeft,
  Save,
  CheckCircle2,
  Rocket,
  BarChart3,
  UserPlus,
  ShieldCheck,
  LockKeyhole,
  Search,
  CircleHelp,
} from "lucide-react";
import { hub, send, FieldValidationError, downloadApplicationReceipt } from "./api";
import { PhoneInput } from './validation/PhoneInput';
import { applicationErrors, contract, passoutYears } from './validation';
import { Logo, formatDate } from "./ui";
import "./application.css";

const states = [
  "Andhra Pradesh",
  "Arunachal Pradesh",
  "Assam",
  "Bihar",
  "Chhattisgarh",
  "Goa",
  "Gujarat",
  "Haryana",
  "Himachal Pradesh",
  "Jharkhand",
  "Karnataka",
  "Kerala",
  "Madhya Pradesh",
  "Maharashtra",
  "Manipur",
  "Meghalaya",
  "Mizoram",
  "Nagaland",
  "Odisha",
  "Punjab",
  "Rajasthan",
  "Sikkim",
  "Tamil Nadu",
  "Telangana",
  "Tripura",
  "Uttar Pradesh",
  "Uttarakhand",
  "West Bengal",
  "Andaman and Nicobar Islands",
  "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi",
  "Jammu and Kashmir",
  "Ladakh",
  "Lakshadweep",
  "Puducherry",
  "Other",
];
type Form = Record<string, string>;
const defaults: Form = {
  employment_type: "Intern",
  department: "",
  portfolio: "",
  github: "",
  full_name: "",
  parent_name: "",
  mobile: "",
  mobile_country_code:'+91',
  email: "",
  identity_type: "Aadhaar",
  identity_number: "",
  gender: "",
  date_of_birth: "",
  city: "",
  state: "",
  tenth_marks: "",
  twelfth_marks: "",
  degree: "",
  current_year: "",
  college: "",
  specialization: "",
  passout_year: "",
  area_of_interest: "",
  skills: "",
  role: "",
  mode: "On-site",
  available_from: "",
  duration: "",
  address: "",
  pincode: "",
  linkedin: "",
  emergency_contact: "",
  emergency_contact_country_code:'+91',
};
type Field = {
  key: string;
  label: string;
  icon: any;
  type?: string;
  placeholder?: string;
  options?: string[];
  required?: boolean;
  span?: string;
};
const baseFields: Field[] = [
  {key:"employment_type",label:"Application Type",icon:Briefcase,options:["Intern","Full-time","Part-time","Contract"]},
  {key:"department",label:"Requested Department",icon:Briefcase,required:false},
  {key:"portfolio",label:"Portfolio URL",icon:Monitor,type:"url",required:false},
  {key:"github",label:"GitHub Profile",icon:Monitor,type:"url",required:false},
  {
    key: "full_name",
    label: "Full Name",
    icon: UserRound,
    placeholder: "Enter your full name",
  },
  {
    key: "parent_name",
    label: "Father / Mother / Guardian Name",
    icon: Users,
    placeholder: "Enter parent / guardian name",
  },
  {
    key: "mobile",
    label: "Mobile Number",
    icon: Phone,
    type: "tel",
    placeholder: "+91 98765 43210",
  },
  {
    key: "email",
    label: "Email Address",
    icon: Mail,
    type: "email",
    placeholder: "Enter your email address",
  },
  {
    key: "identity_type",
    label: "ID Proof Type",
    icon: CreditCard,
    options: ["Aadhaar", "PAN", "Voter ID", "Passport", "Other"],
  },
  {
    key: "identity_number",
    label: "ID Number",
    icon: Hash,
    placeholder: "Enter your ID number",
  },
  {
    key: "gender",
    label: "Gender",
    icon: UserRound,
    type: "radio",
    options: ["Male", "Female", "Other"],
  },
  {
    key: "date_of_birth",
    label: "Date of Birth",
    icon: CalendarDays,
    type: "date",
  },
  { key: "city", label: "City", icon: MapPin, placeholder: "Enter your city" },
  { key: "state", label: "State", icon: MapPin, options: states },
  {
    key: "tenth_marks",
    label: "10th Marks / Percentage",
    icon: GraduationCap,
    type: "number",
    placeholder: "Enter 10th marks / %",
  },
  {
    key: "twelfth_marks",
    label: "12th Marks / Percentage",
    icon: GraduationCap,
    type: "number",
    placeholder: "Enter 12th marks / %",
    required: false,
  },
  {
    key: "degree",
    label: "Current Degree",
    icon: GraduationCap,
    options: [
      "B.Tech / B.E.",
      "B.Sc",
      "B.Com",
      "BBA",
      "BCA",
      "B.A.",
      "M.Tech / M.E.",
      "M.Sc",
      "MBA",
      "MCA",
      "Diploma",
      "Other",
    ],
  },
  {
    key: "current_year",
    label: "Current Year / Semester",
    icon: Layers,
    options: contract.current_years,
  },
  {
    key: "college",
    label: "College / University Name",
    icon: School,
    placeholder: "Enter college / university name",
  },
  {
    key: "specialization",
    label: "Branch / Specialization",
    icon: Settings,
    placeholder: "Enter branch / specialization",
  },
  {
    key: "passout_year",
    label: "Year of Passout",
    icon: CalendarDays,
    options: [],
  },
  {
    key: "area_of_interest",
    label: "Area of Interest",
    icon: Target,
    options: [
      "Software Development",
      "Marketing",
      "Design",
      "Research",
      "Data & Analytics",
      "Human Resources",
      "Finance",
      "Other",
    ],
  },
  {
    key: "skills",
    label: "Skills",
    icon: Settings,
    placeholder: "E.g. Python, Excel, Communication",
  },
  {
    key: "role",
    label: "Internship Role Applying For",
    icon: Briefcase,
    options: [],
  },
  {
    key: "mode",
    label: "Preferred Internship Mode",
    icon: Monitor,
    type: "radio",
    options: ["On-site", "Remote", "Hybrid"],
  },
  {
    key: "available_from",
    label: "Available From",
    icon: CalendarDays,
    type: "date",
  },
  {
    key: "duration",
    label: "Expected Duration",
    icon: Clock,
    options: ["1 Month", "2 Months", "3 Months", "6 Months", "12 Months"],
  },
  {
    key: "address",
    label: "Current Address",
    icon: Home,
    type: "textarea",
    placeholder: "Enter your current address",
    span: "wide",
  },
  {
    key: "pincode",
    label: "PIN Code",
    icon: MapPin,
    placeholder: "Enter 6-digit PIN code",
  },
  {
    key: "linkedin",
    label: "LinkedIn Profile",
    icon: Linkedin,
    type: "url",
    placeholder: "https://www.linkedin.com/in/your-profile",
    required: false,
    span: "wide",
  },
  {
    key: "emergency_contact",
    label: "Emergency Contact Number",
    icon: Phone,
    type: "tel",
    placeholder: "+91 98765 43210",
  },
];

export function PublicHeader() {
  return (
    <><header className="application-header">
      <Link to="/apply" aria-label="Interns Hub home">
        <Logo />
      </Link>
      <nav aria-label="Public navigation">
        <Link to="/apply">Home</Link>
        <a href="/apply#application">Internships</a>
        <a href="/apply#why-interns-hub">For Students</a>
        <Link to="/application-status">Application Status</Link>
      </nav>
    </header><FreeProgramNotice /></>
  );
}
export function FreeProgramNotice() {
  return <aside className="free-program-notice" aria-label="Important internship notice"><ShieldCheck size={22} aria-hidden="true"/><p><strong>Our internship program is completely free.</strong> If anyone asks you to pay a fee for this program, please report it to <a href="tel:9618222220">9618222220</a>.</p></aside>;
}

function ReceiptDownload({ receipt }: { receipt: any }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <div className="receipt-download"><button className="button" type="button" disabled={busy} onClick={async () => {
    setBusy(true); setError("");
    try { await downloadApplicationReceipt(receipt.receipt_token, receipt.reference); }
    catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  }}>{busy ? "Preparing receipt…" : "Download application receipt (PDF)"}</button>{error && <p role="alert" className="error">{error}</p>}</div>;
}
function Footer() {
  return (
    <footer className="application-footer">
      <Logo />
      <div>
        <Link to="/apply">Internship Application</Link>
        <Link to="/application-status">Check Status</Link>
        <Link to="/login">Intern Login</Link>
      </div>
      <p>
        <CircleHelp size={18} />
        Need help? Contact your HRMS team.
      </p>
    </footer>
  );
}
function Promo() {
  return (
    <aside className="application-promo" id="why-interns-hub">
      <span className="build-pill">🚀 Build Your Future</span>
      <h1>
        Kickstart Your
        <br />
        Career with
        <br />
        <span>
          Real-World
          <br />
          Experience
        </span>
      </h1>
      <p>
        Join our internship program and gain hands-on experience, learn from
        industry experts, and turn your skills into opportunities.
      </p>
      <div className="benefits">
        {[
          [
            Briefcase,
            "Industry Exposure",
            "Work on real projects and build practical skills.",
          ],
          [Users, "Mentorship", "Get guidance from experienced professionals."],
          [
            BarChart3,
            "Career Growth",
            "Boost your profile and unlock future opportunities.",
          ],
        ].map(([Icon, title, description]) => {
          const I = Icon as any;
          return (
            <div key={String(title)}>
              <span>
                <I size={25} />
              </span>
              <div>
                <b>{String(title)}</b>
                <p>{String(description)}</p>
              </div>
            </div>
          );
        })}
      </div>
      <div
        className="application-art"
        role="img"
        aria-label="Students learning together"
      />
      <small className="promo-note">
        Ideas. Skills. Opportunities.
        <br />A brighter you.
      </small>
    </aside>
  );
}
function ApplicationField({
  field,
  value,
  onChange,
  countryCode,onCountryCodeChange,error,onBlur,readOnly,today,
}: {
  field: Field;
  value: string;
  today: string;
  readOnly?: boolean;
  onChange: (value: string) => void;
  countryCode?:string;onCountryCodeChange?:(value:string)=>void;error?:string;onBlur?:()=>void;
}) {
  const { key, label, icon: Icon, type, options, placeholder } = field;
  const required = field.required !== false;
  const max =
    key === "date_of_birth" ? new Date(Date.parse(today+'T00:00:00Z')-86400000).toISOString().slice(0,10) : undefined;
  const min =
    key === "available_from"
      ? today
      : type === "number"
        ? "0"
        : undefined;
  return (
    <div className={`application-field ${field.span || ""}`}>
      <label htmlFor={`application-${key}`}>
        <Icon size={15} />
        {label}
        {required ? (
          <span className="required">*</span>
        ) : (
          <small>(Optional)</small>
        )}
      </label>
      {type==='tel'?<PhoneInput id={`application-${key}`} label={label} value={value} countryCode={countryCode||''} onChange={onChange} onCountryCodeChange={onCountryCodeChange!} required={required} error={error} onBlur={onBlur}/>:type === "radio" ? (
        <fieldset id={`application-${key}`} tabIndex={-1} className="application-radios" aria-invalid={!!error} aria-describedby={error?`application-${key}-error`:undefined}>
          <legend className="sr-only">{label}</legend>
          {options?.map((option) => (
            <label key={option}>
              <input
                type="radio"
                name={key}
                required={required}
                checked={value === option}
                value={option}
                onBlur={onBlur}
                onChange={() => onChange(option)}
              />
              {option}
            </label>
          ))}
        </fieldset>
      ) : options ? (
        <select
          id={`application-${key}`}
          required={required}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur} aria-invalid={!!error} aria-describedby={error?`application-${key}-error`:undefined}
        >
          <option value="">Select {label.toLowerCase()}</option>
          {options.map((option) => (
            <option key={option}>{option}</option>
          ))}
        </select>
      ) : type === "textarea" ? (
        <textarea
          id={`application-${key}`}
          rows={3}
          maxLength={200}
          required={required}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur} aria-invalid={!!error} aria-describedby={error?`application-${key}-error`:undefined}
          placeholder={placeholder}
        />
      ) : (
        <input
          id={`application-${key}`}
          type={type || "text"}
          readOnly={readOnly}
          inputMode={key === 'pincode' ? 'numeric' : undefined}
          pattern={key === 'pincode' ? '[1-9][0-9]{5}' : undefined}
          required={required}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur} aria-invalid={!!error} aria-describedby={error?`application-${key}-error`:undefined}
          placeholder={placeholder}
          maxLength={
            key === 'pincode' ? 6 : key === "identity_number" ? 40 : key === "skills" ? 1000 : ['full_name','parent_name'].includes(key)?160:key==='email'?150:['city','state'].includes(key)?100:key==='specialization'?150:200
          }
          min={min}
          max={type === "number" ? "100" : max}
          step={type === "number" ? "0.01" : undefined}
          autoComplete={
            key === 'pincode' ? 'postal-code' : key === "email"
              ? "email"
              : key === "full_name"
                ? "name"
                : key === "mobile"
                  ? "tel"
                  : "off"
          }
        />
      )}
      {key === 'address' && <small className="address-counter">{value.length}/200 characters</small>}
      {error&&type!=='tel'&&<small id={`application-${key}-error`} role="alert" style={{color:'#b42318'}}>{error}</small>}
    </div>
  );
}

export function ApplicationPage({applicant}:{applicant:{email:string;full_name:string;details?:Record<string,unknown>}}) {
  const draftKey = `internhub.application-draft:${applicant.email.toLowerCase()}`;
  const [form, setForm] = useState<Form>(defaults);
  const [step, setStep] = useState(0);
  const [documents,setDocuments]=useState<Array<{token:string;name:string;category:string}>>([]);
  const [documentCategory,setDocumentCategory]=useState("Identity");
  const correcting=new URLSearchParams(window.location.search).get("correction")==="1";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [consent, setConsent] = useState(false);
  const [accountAttempted,setAccountAttempted]=useState(false);
  const accountErrors={password:password.length<8||new TextEncoder().encode(password).length>72?'Use at least 8 characters and no more than 72 UTF-8 bytes.':'',confirm:password!==confirm?'Your passwords do not match.':'',consent:!consent?'Consent is required to submit your application.':''};
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState<any>();
  const [roles, setRoles] = useState<string[]>([]);
  const [serverToday,setServerToday]=useState(new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Kolkata'}));
  const [touched,setTouched]=useState<Record<string,boolean>>({});
  const [attempted,setAttempted]=useState(false);
  const [serverErrors,setServerErrors]=useState<Record<string,string>>({});
  const submitting=useRef(false);
  const formRef = useRef<HTMLFormElement>(null);
  useEffect(() => {
    document.title = "Apply for an Internship · Interns Hub";
    hub("/application-options")
      .then((r) => {setRoles(r.roles);if(r.today)setServerToday(r.today);})
      .catch(() => setError("Application roles could not be loaded. Please refresh before applying."));
    try {
      const draft = sessionStorage.getItem(draftKey);
      if (draft) {
        const restored=JSON.parse(draft);
        for(const field of ['mobile','emergency_contact'])if(restored[field]&&!restored[field+'_country_code'])restored[field+'_country_code']='';
        setForm({ ...defaults, ...restored });
        setNotice("Your saved draft has been restored.");
      }
    } catch {}
    if (applicant.email) {
      const saved = Object.fromEntries(Object.entries(applicant.details || {}).filter(([key])=>key in defaults && key !== 'identity_number').map(([key,value])=>[key,value == null ? '' : String(value)]));
      setForm(current=>({...current,...saved,email:applicant.email,full_name:applicant.full_name || current.full_name}));
      setNotice("Your account details are ready. Complete your application below; approval is required before intern access.");
    }
  }, []);
  const errors={...applicationErrors(form,roles,serverToday),...serverErrors};
  const choiceMap:Record<string,string[]>={degree:contract.degrees,current_year:contract.current_years,state:contract.states,area_of_interest:contract.areas,passout_year:passoutYears(serverToday)};
  const fields=baseFields.map(field=>({...field,options:field.key==='role'?roles:choiceMap[field.key]||field.options}));
  function change(key:string,value:string){setForm(current=>({...current,[key]:value}));setServerErrors(current=>{const next={...current};delete next[key];return next;});}
  function focusError(issues:Record<string,string>){const first=baseFields.find(field=>issues[field.key]);if(first)document.getElementById(`application-${first.key}`)?.focus();}
  function saveDraft() {
    const { identity_number, ...safe } = form;
    sessionStorage.setItem(draftKey, JSON.stringify(safe));
    setNotice(
      "Draft saved in this browser tab. Your ID number and password are not saved.",
    );
  }
  function review() {
    setError("");
    setAttempted(true);
    if(Object.keys(errors).length){focusError(errors);return;}
    if (formRef.current?.reportValidity()) {
      setStep(1);
      document
        .getElementById("application")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
  async function submit() {
    if(submitting.current)return;
    const issues=applicationErrors(form,roles,serverToday);
    if(Object.keys(issues).length){setAttempted(true);setStep(0);setError('Correct your application details before submitting.');return;}
    setAccountAttempted(true);
    const firstAccountError=Object.entries(accountErrors).find(([,message])=>message);
    if(firstAccountError){document.getElementById('application-'+firstAccountError[0])?.focus();return;}
    setBusy(true);
    submitting.current=true;
    setError("");
    try {
      const payload = {
          ...form,
          email: form.email,
          tenth_marks: Number(form.tenth_marks),
          twelfth_marks:
            form.twelfth_marks === "" ? null : Number(form.twelfth_marks),
          passout_year: Number(form.passout_year),
          linkedin: form.linkedin.trim() || null,
          password,
          consent,
          document_tokens:documents.map(d=>d.token),
          portfolio:form.portfolio.trim()||null,
          github:form.github.trim()||null,
        };
      const result = await hub(correcting?"/applications/corrections":"/applications",send("POST",correcting?{credentials:{email:form.email.trim(),password},application:payload}:payload));
      setReceipt(result);
      setPassword("");
      setConfirm("");
      setForm(defaults);
      sessionStorage.removeItem(draftKey);
      setStep(2);
    } catch (e) {
      if(e instanceof FieldValidationError){setServerErrors(e.fields);setAttempted(true);setStep(0);}
      setError((e as Error).message);
    } finally {
      setBusy(false);
      submitting.current=false;
    }
  }
  return (
    <div className="application-page">
      <PublicHeader />
      <main className="application-layout">
        <Promo />
        <section className="application-panel" id="application">
          <ol className="application-steps">
            {["Intern Registration", "Review Details", "Submit"].map(
              (label, i) => (
                <li
                  key={label}
                  className={`${i === step ? "current" : ""} ${i < step ? "complete" : ""}`}
                  aria-current={i === step ? "step" : undefined}
                >
                  <span>{i < step ? <CheckCircle2 size={19} /> : i + 1}</span>
                  <b>{label}</b>
                </li>
              ),
            )}
          </ol>
          {step === 2 ? (
            <div className="application-success">
              <span className="success-mark">
                <CheckCircle2 size={45} />
              </span>
              <h1>Application Submitted!</h1>
              <p>
                Thank you for applying to Interns Hub. Your HRMS team will
                review your application.
              </p>
              <div className="application-receipt">
                <small>YOUR APPLICATION REFERENCE</small>
                <strong>{receipt?.reference}</strong>
                <span className="badge orange">Pending Approval</span>
              </div>
              {receipt?.receipt_token && <ReceiptDownload receipt={receipt}/>}
              <p>
                Once approved, your intern account will be activated and your
                unique intern ID will be available. Sign in with the email and
                password you chose.
              </p>
              <Link className="button" to="/application-status">
                Check Application Status
                <ArrowRight size={17} />
              </Link>
              <Link className="text-link" to="/login">
                Back to Intern Login
              </Link>
            </div>
          ) : (
            <>
              <div className="application-title">
                <span>
                  <UserPlus size={26} />
                </span>
                <div>
                  <h2>
                    {step === 0
                      ? "Join Our Internship Program"
                      : "Review Your Application"}
                  </h2>
                  <p>
                    {step === 0
                      ? "Register your details to apply for internship opportunities"
                      : "Check your details and set up your intern login before submitting."}
                  </p>
                </div>
              </div>
              {notice && (
                <div className="application-notice" role="status">
                  <Save size={17} />
                  {notice}
                </div>
              )}
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              <form
                noValidate
                ref={formRef}
                onSubmit={(e) => {
                  e.preventDefault();
                  step === 0 ? review() : submit();
                }}
              >
                {step === 0 ? (
                  <div className="application-field-groups">
                    {attempted&&Object.keys(errors).length>0&&<div className="application-validation-summary" style={{gridColumn:"1 / -1"}} role="alert" tabIndex={-1}><p>Please correct the highlighted fields.</p><ul>{fields.filter(field=>errors[field.key]).map(field=><li key={field.key}><a href={`#application-${field.key}`} onClick={()=>document.getElementById(`application-${field.key}`)?.focus()}>{field.label}: {errors[field.key]}</a></li>)}</ul></div>}
                    {[
                      {name:"Personal details",keys:["full_name","parent_name","mobile","email","identity_type","identity_number","gender","date_of_birth"]},
                      {name:"Education",keys:["degree","current_year","college","specialization","passout_year","tenth_marks","twelfth_marks"]},
                      {name:"Internship preferences",keys:["employment_type","department","role","area_of_interest","skills","mode","available_from","duration","portfolio","github","linkedin"]},
                      {name:"Address & emergency contact",keys:["address","city","state","pincode","emergency_contact"]},
                    ].map(group => <fieldset className="application-field-group" key={group.name}>
                      <legend>{group.name}</legend><div className="application-fields">
                        {fields.filter(field => group.keys.includes(field.key)).map((field) => (
                      <ApplicationField
                        key={field.key}
                        today={serverToday}
                        field={{...field,span:group.name === "Personal details" ? "half" : field.span}}
                        value={form[field.key]}
                        readOnly={field.key === "email"}
                        onChange={value=>change(field.key,value)}
                        onBlur={()=>setTouched(current=>({...current,[field.key]:true}))}
                        error={attempted||touched[field.key]?errors[field.key]:undefined}
                        countryCode={form[field.key+'_country_code']}
                        onCountryCodeChange={value=>change(field.key+'_country_code',value)}
                      />
                    ))}
                      </div></fieldset>)}
                  </div>
                ) : (
                  <>
                    <div className="application-review">
                      {fields.map((field) => (
                        <div key={field.key}>
                          <dt>{field.label}</dt>
                          <dd>
                            {field.key === "identity_number"
                              ? `•••• ${form.identity_number.slice(-4)}`
                              : field.type === "date"
                                ? formatDate(form[field.key])
                                : field.type==='tel'?`${form[field.key+'_country_code']} ${form[field.key]}`:form[field.key] || "Not provided"}
                          </dd>
                        </div>
                      ))}
                    </div>
                    <section className="application-account"><h3>Private supporting documents (optional)</h3><p>PDF, PNG, JPG or DOCX; up to 10 files, 10 MB each. Files are visible only to authorized HR reviewers.</p><label>Document category<select aria-label="Document category" value={documentCategory} onChange={e=>setDocumentCategory(e.target.value)}>{['Identity','Academic','Resume','Portfolio'].map(c=><option key={c}>{c}</option>)}</select></label><label>Upload supporting documents<input aria-label="Upload supporting documents" type="file" accept=".pdf,.png,.jpg,.jpeg,.docx" multiple disabled={busy||documents.length>=10} onChange={async e=>{setBusy(true);try{if(documents.length+(e.target.files?.length||0)>10)throw new Error('Upload up to 10 documents in total');for(const file of Array.from(e.target.files||[])){if(file.size>10*1024*1024)throw new Error('Maximum file size is 10 MB');const body=new FormData();body.append('file',file);body.append('category',documentCategory);const result=await hub('/application-uploads',{method:'POST',body});setDocuments(ds=>[...ds,result]);}}catch(err){setError((err as Error).message)}finally{setBusy(false)}}}/></label>{documents.map(d=><p key={d.token}>{d.category}: {d.name}<button type="button" onClick={()=>setDocuments(ds=>ds.filter(x=>x.token!==d.token))}>Remove</button></p>)}</section>
                    <div className="application-account">
                      <h3>
                        <LockKeyhole size={18} />
                        Set Up Your Intern Login
                      </h3>
                      <p>
                        Use this password after HRMS approves your application.
                        Your account is not active until approval.
                      </p>
                      <div className="application-passwords">
                        <label>
                          Choose Password *
                          <input
                            type="password"
                            autoComplete="new-password"
                            minLength={8}
                            maxLength={72}
                            required
                            id="application-password" aria-invalid={accountAttempted&&!!accountErrors.password} aria-describedby="application-password-error"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            placeholder="At least 8 characters"
                          />
                          {accountAttempted&&accountErrors.password&&<small id="application-password-error" role="alert">{accountErrors.password}</small>}
                        </label>
                        <label>
                          Confirm Password *
                          <input
                            type="password"
                            autoComplete="new-password"
                            minLength={8}
                            maxLength={72}
                            required
                            id="application-confirm" aria-invalid={accountAttempted&&!!accountErrors.confirm} aria-describedby="application-confirm-error"
                            value={confirm}
                            onChange={(e) => setConfirm(e.target.value)}
                            placeholder="Re-enter your password"
                          />
                          {accountAttempted&&accountErrors.confirm&&<small id="application-confirm-error" role="alert">{accountErrors.confirm}</small>}
                        </label>
                      </div>
                      <label className="application-consent">
                        <input
                          type="checkbox"
                          required
                          id="application-consent" aria-invalid={accountAttempted&&!!accountErrors.consent} aria-describedby="application-consent-error"
                          checked={consent}
                          onChange={(e) => setConsent(e.target.checked)}
                        />
                        <span>
                          I declare that the information provided is correct and
                          consent to its use for reviewing my internship
                          application. <span className="required">*</span>
                        </span>
                      </label>
                      {accountAttempted&&accountErrors.consent&&<small id="application-consent-error" role="alert">{accountErrors.consent}</small>}
                    </div>
                  </>
                )}
                <div className="application-actions">
                  {step === 1 && (
                    <button
                      type="button"
                      className="button outline"
                      onClick={() => setStep(0)}
                    >
                      <ArrowLeft size={16} />
                      Edit Details
                    </button>
                  )}
                  <button
                    type="button"
                    className="button outline"
                    onClick={saveDraft}
                  >
                    <Save size={16} />
                    Save Draft
                  </button>
                  <button className="button" disabled={busy}>
                    {busy
                      ? "Submitting…"
                      : step === 0
                        ? "Review Application"
                        : "Submit Application"}
                    <ArrowRight size={17} />
                  </button>
                </div>
                <div className="application-assurance">
                  <ShieldCheck size={14} />
                  <span>
                    Supporting documents are optional and stored privately for HR review.
                  </span>
                </div>
              </form>
            </>
          )}
        </section>
      </main>
      <Footer />
    </div>
  );
}

export function ApplicationStatus() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [result, setResult] = useState<any>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="application-page">
      <PublicHeader />
      <main className="status-layout">
        <section className="application-panel">
          <div className="application-title">
            <span>
              <Search size={25} />
            </span>
            <div>
              <h1>Application Status</h1>
              <p>Use the email and password you chose when applying.</p>
            </div>
          </div>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              setResult(undefined);
              try {
                setResult(
                  await hub(
                    "/applications/status",
                    send("POST", { email, password }),
                  ),
                );
                setPassword("");
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Email Address
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              Application Password
              <input
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <button disabled={busy} className="button full">
              {busy ? "Checking…" : "Check Application Status"}
              <ArrowRight size={17} />
            </button>
          </form>
          {result && (
            <div className="status-result" role="status">
              <span
                className={`badge ${result.status === "Approved" ? "green" : "orange"}`}
              >
                {result.status}
              </span>
              <p>
                Reference: <b>{result.reference}</b>
              </p>
              {result.intern_id && (
                <div className="application-receipt">
                  <small>YOUR UNIQUE INTERN ID</small>
                  <strong>{result.intern_id}</strong>
                </div>
              )}
              <p>
                {result.status === "Pending"
                  ? "Your application is awaiting HRMS review. Login becomes available after approval."
                  : result.status === "Approved"
                    ? "Your account is ready. Sign in with your application email and password."
                    : result.status === "Correction Requested"
                      ? "Please submit the corrections requested by the review team."
                    : "Your application was not approved."}
              </p>
              {result.review_note && <p>{result.review_note}</p>}
              {result.correction_deadline && <p><strong>Correction deadline: {formatDate(result.correction_deadline)}</strong> (India time). Daily email reminders start three days before the deadline.</p>}
              {result.receipt_token && <ReceiptDownload receipt={result}/>}
              {result.status==="Correction Requested" && <Link className="button" to="/apply?correction=1">Submit corrected application</Link>}
              {result.history?.map((event:any,index:number)=><p key={index}>{event.state} · {event.note||formatDate(event.created_at?.slice(0,10))}</p>)}
              {result.can_login && (
                <Link className="button full" to="/login">
                  Log In to Interns Hub
                  <ArrowRight size={16} />
                </Link>
              )}
            </div>
          )}
          <p className="status-bottom">
            Haven't applied yet?{" "}
            <Link to="/apply">Apply for an internship</Link>
          </p>
        </section>
      </main>
      <Footer />
    </div>
  );
}
