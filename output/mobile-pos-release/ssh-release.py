import paramiko,getpass,json,sys,base64
c=paramiko.SSHClient();c.load_system_host_keys();c.set_missing_host_key_policy(paramiko.RejectPolicy())
c.connect('139.59.91.37',username='root',password=getpass.getpass('Server password: '),timeout=20,allow_agent=False,look_for_keys=False)
c.get_transport().set_keepalive(20)
print('CONNECTED',flush=True)
for line in sys.stdin:
 try:
  q=json.loads(line)
  if q.get('op')=='upload':
   with c.open_sftp() as s:s.put(q['local'],q['remote'])
   print(json.dumps({'uploaded':q['remote']}),flush=True)
  elif q.get('op')=='download':
   with c.open_sftp() as s:s.get(q['remote'],q['local'])
   print(json.dumps({'downloaded':q['local']}),flush=True)
  elif q.get('op')=='exec':
   i,o,e=c.exec_command(q['cmd'],timeout=600)
   for b in iter(lambda:o.readline(),''):print(b,end='',flush=True)
   print(e.read().decode(),end='',flush=True);print('EXIT '+str(o.channel.recv_exit_status()),flush=True)
  elif q.get('op')=='close':break
 except Exception as ex: print(type(ex).__name__+': '+str(ex),flush=True)
c.close()
