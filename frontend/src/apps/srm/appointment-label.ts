type AppointmentIdentity = {customer_id?:number;data:Record<string,unknown>};
const text=(value:unknown)=>typeof value==='string'?value.trim():'';
export const appointmentService=(row:AppointmentIdentity)=>text(row.data.service_name)||'Service';
export const appointmentCustomer=(row:AppointmentIdentity)=>text(row.data.customer_name)||(row.customer_id?`Customer #${row.customer_id}`:'Customer');
export const appointmentLabel=(row:AppointmentIdentity)=>`${appointmentService(row)} · ${appointmentCustomer(row)}`;
