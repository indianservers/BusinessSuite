// Visual fixtures transcribed from the user's three screenshots. Never written to live records.
const date='2026-11-17';
const at=time=>`${date}T${time}:00+05:30`;
const woman='/images/scheduling/portrait-woman.png', man='/images/scheduling/portrait-man.png';
const base={timezone:'Asia/Kolkata',opens:'09:00',closes:'19:00',capacity:1,weekdays:[0,1,2,3,4],assigned_color:'Lavender'};
const breakTime=JSON.stringify([{starts_at:at('12:00'),ends_at:at('13:30'),label:'Lunch'}]);
function resource(id,title,type,location='Ground floor',status='active',extra={}){return {id,title,kind:'resource',revision:1,status,data:{...base,resource_type:type,location,...extra}};}
function visit(id,name,service,time,minutes,status,resource_ids,extra={}){return {id,kind:'appointment',revision:1,title:name,status,customer_id:id+1000,data:{customer_name:name,customer_avatar_url:/Arjun/.test(name)?man:woman,service_name:service,starts_at:at(time),duration_minutes:minutes,resource_ids,...extra}};}
const resources=[
  resource(1,'Anita Rao','provider','Ground floor','active',{employee_id:21,avatar_url:woman}),
  resource(2,'Rahul Kumar','provider','Ground floor','active',{employee_id:22,avatar_url:man,unavailable_intervals:breakTime}),
  resource(3,'Priya Shah','provider','Ground floor','active',{employee_id:23,avatar_url:woman,unavailable_intervals:breakTime}),
  resource(10,'Chair 01','chair'),resource(11,'Chair 02','chair','Ground floor','active',{unavailable_intervals:breakTime}),
  resource(12,'Treatment Room 01','room','First floor','active',{unavailable_intervals:breakTime}),
  resource(13,'Consultation Room','room','First floor','active',{unavailable_intervals:breakTime}),
  resource(14,'Meeting Room','room','First floor'),resource(15,'Equipment Kit','equipment','Ground floor','maintenance'),
  ...Array.from({length:6},(_,i)=>resource(16+i,`Studio ${String(i+1).padStart(2,'0')}`,i<3?'room':'equipment',i%2?'First floor':'Ground floor')),
];
const schedule=[
  visit(100,'Meera Nair','Hair styling','09:00',60,'checked_in',[1,10]),
  visit(101,'Arjun Rao','Consultation','09:45',90,'booked',[2,13]),
  visit(102,'Kavya Reddy','Therapy','10:30',90,'completed',[3,12]),
  visit(103,'Sneha Das','Consultation','14:00',45,'pending',[3,13]),
  visit(104,'Rohan Mehta','Hair cut','12:00',90,'booked',[1]),
  visit(105,'Isha Verma','Hair coloring','14:00',90,'completed',[1]),
  visit(106,'Nikhil Jain','Therapy','14:00',100,'checked_in',[2]),
  visit(107,'Vikram S.','Therapy','15:00',90,'booked',[3],{conflict_resource_ids:[3]}),
  visit(108,'Riya Kapoor','Hair cut','13:00',85,'booked',[10]),
  visit(109,'Dev Malhotra','Hair styling','10:00',80,'booked',[11]),
  visit(110,'Aman Gupta','Hair cut','15:00',90,'completed',[11]),
  visit(111,'Vikram S.','Therapy','14:00',75,'booked',[12]),
  visit(112,'Sneha Das','Consultation','15:00',90,'pending',[13]),
];
// Remaining permitted bookings are on off-screen physical resources, matching the 24-record header.
for(let i=0;schedule.length<24;i++)schedule.push(visit(200+i,`Customer ${i+1}`,'Service',`${String(9+Math.floor(i/2)).padStart(2,'0')}:${i%2?'30':'00'}`,30,i<4?'checked_in':i<6?'cancelled':'completed',[16+i%6]));
// Match the screenshot's aggregate state counts while keeping its visible rows unchanged.
schedule[7].status='completed';schedule[8].status='completed';schedule[9].status='checked_in';schedule[11].status='completed';
for(const row of schedule.slice(13))if(row.status==='completed')row.status='completed';
const desired={checked_in:6,completed:12,cancelled:2};
for(const status of ['checked_in','cancelled','completed']){
  let missing=desired[status]-schedule.filter(r=>r.status===status).length;
  for(const row of schedule.slice(13))if(missing>0&&row.status!==status&&schedule.filter(r=>r.status===row.status).length>(desired[row.status]||0)){row.status=status;missing--;}
}
// Lane reservations include setup/cleanup buffers; the upcoming table keeps service times.
const reservation=(id,lanes)=>{schedule.find(row=>row.id===id).data.timeline_reservations=JSON.stringify(lanes.map(([resource_id,time,duration_minutes,status,hidden])=>({resource_id,...(time?{starts_at:at(time)}:{}),duration_minutes,status,hidden})));};
reservation(100,[[1,'09:00',90,'checked_in'],[10,'09:00',90,'checked_in']]);
reservation(101,[[2,'09:38',91,'booked'],[13,'09:00',90,'booked']]);
reservation(102,[[3,'10:13',94,'completed'],[12,'10:24',95,'completed']]);
reservation(103,[[3,'13:40',74,'booked'],[13,null,null,null,true]]);
reservation(107,[[3,'15:05',84,'booked']]);
reservation(108,[[10,'13:00',85,'booked']]);
reservation(109,[[11,'09:56',77,'booked']]);
reservation(110,[[11,'15:00',86,'completed']]);
reservation(111,[[12,'14:00',76,'booked']]);
reservation(112,[[13,'15:00',86,'pending']]);
const resourceBookings=[];
const counts=[2,3,5,2,3],totals=[0,198,102,300,150];
for(let r=0;r<5;r++)for(let n=0;n<counts[r];n++)resourceBookings.push(visit(400+r*10+n,`Resource customer ${r}-${n}`,'Service',r===1&&n===0?'11:00':`${String(13+n).padStart(2,'0')}:00`,r===0?30:n===counts[r]-1?totals[r]-Math.floor(totals[r]/counts[r])*(counts[r]-1):Math.floor(totals[r]/counts[r]),r===0?'completed':r===1&&n===0?'in_service':'booked',[10+r]));
resourceBookings.push(visit(490,'In progress A','Service','11:00',60,'in_service',[16]),visit(491,'In progress B','Service','11:00',60,'in_service',[17]));
const customer={id:8,name:'Meera Nair',phone:'9876543210',phone_country_code:'+91',avatar_url:'/images/scheduling/portrait-customer.png',entityKind:'Individual',roles:['Customer']};
const service={id:9,kind:'service',name:'Hair styling',code:'HAIR',category:'Hair',price:1200,currency:'INR',tax:0};
const bookingResources=[resource(4,'Rahul Kumar','provider','Ground floor','active',{employee_id:24,avatar_url:man}),resource(5,'Priya Shah','provider','Ground floor','active',{employee_id:25,avatar_url:woman}),resource(6,'Riya Mehta','provider','Ground floor','active',{employee_id:26,avatar_url:woman}),resources[0],...resources.filter(r=>r.id>=10)];
const bookingRows=[visit(601,'Customer A','Hair cut','10:00',60,'completed',[1]),visit(602,'Customer B','Hair spa','12:30',60,'booked',[1]),visit(604,'Customer D','Blow dry','16:30',60,'booked',[1])];
module.exports={at,resources,schedule,resourceBookings,customer,service,bookingResources,bookingRows,profile:{id:1,name:'Aditi Sharma',email:'aditi@example.invalid',avatar_url:'/images/scheduling/portrait-profile.png',role:'super_admin',is_superuser:true,access:{companyName:'Indian Servers',companyId:1,isAccessAdmin:true,isGlobalAdmin:true,managed:false,grants:{},modules:[],memberships:[1]}}};
