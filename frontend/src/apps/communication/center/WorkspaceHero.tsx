import { useQuery } from '@tanstack/react-query';
import { MessageCircle, ShieldCheck, Send, Inbox } from 'lucide-react';
import { Link } from 'react-router-dom';
import { api } from '@/services/api';
import { whatsappBase, type Status } from '../whatsapp/types';
import { useCenterScope } from './shared';

export default function WorkspaceHero() {
  const scope=useCenterScope();
  const account=useQuery({queryKey:['whatsapp',scope,'status'],queryFn:async()=>(await api.get<Status>(whatsappBase+'/status')).data,staleTime:60000});
  const connected=account.data?.configured;
  return <div className="cc-premium-hero"><span className="cc-hero-emblem"><MessageCircle size={34}/></span><div className="cc-hero-copy"><small>INDIAN SERVERS · BUSINESS SUITE</small><h1>Communication Center</h1><p>Unified messaging, customer conversations, campaigns and automations in one intelligent workspace.</p><div className="cc-hero-actions"><Link to="/crm/communication-hub?section=inbox"><Inbox size={14}/>Open inbox</Link><Link to="/crm/emails"><Send size={14}/>New message</Link></div></div><Link className="cc-live-connection" to="/crm/whatsapp/settings"><ShieldCheck size={20}/><span><strong>{account.isPending?'Checking WhatsApp…':account.isError?'Connection unavailable':connected?'WhatsApp configured':'WhatsApp setup required'}</strong><small>{account.data?.connection?.displayNumber || (connected?'Existing sender configuration':'View channel settings')}</small></span><i className={connected?'is-connected':''}/></Link></div>;
}
