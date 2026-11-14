import PrivateSavedViews from '@/shared/records/PrivateSavedViews';
export type TicketView={status:string;priority:string;assigned_to_me:boolean;my_tickets:boolean};
export default function TicketSavedViews(props:{scope:string;filters:TicketView;onApply:(view:TicketView)=>void}){
 return <PrivateSavedViews {...props} endpoint="/helpdesk/ticket-views" title="Private HR helpdesk views" itemLabel="ticket" recordLabel="Tickets"/>;
}
