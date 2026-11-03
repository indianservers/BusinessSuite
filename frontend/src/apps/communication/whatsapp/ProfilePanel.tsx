import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { whatsappBase as base, whatsappError } from "./types";
type Profile={profile_picture_url?:string;about?:string;description?:string;address?:string;email?:string;websites?:string[];vertical?:string};
export default function ProfilePanel({scope,admin}:{scope:string;admin:boolean}) {
  const profile=useQuery({queryKey:['whatsapp',scope,'profile'],queryFn:async()=>(await api.get<Profile>(base+'/profile')).data});
  const [file,setFile]=useState<File|null>(null),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  async function upload(){
    if(!file)return;setBusy(true);setNotice('');
    try{const data=new FormData();data.append('file',file);await api.post(base+'/profile/picture',data);await profile.refetch();setFile(null);setNotice('Profile photo submitted to Meta. The photo below is read from Meta; WhatsApp clients may take time to refresh their cached copy.');}
    catch(error){setNotice(whatsappError(error));}
    finally{setBusy(false);}
  }
  return <section className="space-y-4 rounded-xl border p-5"><h3 className="font-medium">WhatsApp business profile</h3>
    <p className="text-sm text-muted-foreground">This is the connected WhatsApp number’s profile. A Facebook app logo or Business Suite avatar does not set this photo.</p>
    {profile.isPending&&<p>Reading profile from Meta…</p>}{profile.isError&&<p role="alert">{whatsappError(profile.error)}</p>}
    {profile.data&&<div className="flex flex-wrap gap-5">{profile.data.profile_picture_url?<img className="h-32 w-32 rounded-full border object-cover" src={profile.data.profile_picture_url} alt="Current WhatsApp business profile"/>:<p className="rounded-lg border p-4 text-sm">Meta currently has no profile photo for this WhatsApp number.</p>}
      <div className="max-w-2xl space-y-2 text-sm"><p>{profile.data.about}</p><p>{profile.data.description}</p><p>{profile.data.email}</p><p>{profile.data.address}</p>{profile.data.websites?.map(site=><p key={site}>{site}</p>)}</div></div>}
    {admin&&<div className="space-y-2 border-t pt-4"><label className="block text-sm">Upload profile photo<input className="mt-2 block w-full text-sm" type="file" accept="image/jpeg" disabled={busy} onChange={e=>setFile(e.target.files?.[0]||null)}/></label><p className="text-xs text-muted-foreground">Square JPEG, 192–4096 pixels, up to 2 MB. This updates the public WhatsApp business photo.</p><Button disabled={busy||!file} onClick={()=>void upload()}>{busy?'Updating Meta…':'Update WhatsApp photo'}</Button></div>}
    <Button variant="outline" disabled={busy} onClick={()=>void profile.refetch()}>Refresh profile from Meta</Button>{notice&&<p role="status" className="text-sm">{notice}</p>}
  </section>;
}
