import {afterEach,describe,expect,it,vi} from 'vitest';
import {api} from './api';
afterEach(()=>vi.unstubAllGlobals());
describe('report API integration contract',()=>{
 it('establishes a session before creation and reuses the creation key after a lost response',async()=>{
  let healthAttempts=0,postAttempts=0;
  const fetcher=vi.fn().mockImplementation(async(url:string)=>{
   if(url==='/api/health'){if(++healthAttempts===1)throw new TypeError('offline');return new Response('{}',{status:200});}
   if(++postAttempts===1)throw new TypeError('lost response');return new Response('{"id":"same-report"}',{status:201});
  });vi.stubGlobal('fetch',fetcher);
  const data={creation_key:'stable-draft-key',plate:'А123ВС77'} as Parameters<typeof api.create>[0];
  await expect(api.create(data)).rejects.toThrow('Нет связи');
  await expect(api.create(data)).rejects.toThrow('Нет связи');
  await expect(api.create(data)).resolves.toEqual({id:'same-report'});
  expect(fetcher.mock.calls.map(call=>call[0])).toEqual(['/api/health','/api/health','/api/reports','/api/reports']);
  for(const call of fetcher.mock.calls){const options=call[1];expect(options.credentials).toBe('include');if(call[0]==='/api/reports'){expect(options.headers['Idempotency-Key']).toBe('stable-draft-key');expect(JSON.parse(options.body)).toEqual({plate:'А123ВС77'});}}
 });
 it('sends editable values only and includes session credentials',async()=>{
  const fetcher=vi.fn().mockResolvedValue(new Response(JSON.stringify({id:'abc',plate:'А123ВС77'}),{status:200,headers:{'Content-Type':'application/json'}}));vi.stubGlobal('fetch',fetcher);
  await api.update('abc',{id:'abc',created_at:'old',updated_at:'old',photos:{scene:{}},plate:'А123ВС77',confirmed:true});
  const [url,options]=fetcher.mock.calls[0];expect(url).toBe('/api/reports/abc');expect(options.credentials).toBe('include');expect(JSON.parse(options.body)).toEqual({plate:'А123ВС77',confirmed:true});
 });
 it('sends bounded chunks with the original bytes, source and checksum',async()=>{
  const fetcher=vi.fn().mockImplementation(async()=>new Response('{"id":"abc"}',{status:200}));vi.stubGlobal('fetch',fetcher);const photo=new Blob([new Uint8Array(700000).fill(42)],{type:'image/jpeg'});
  await api.upload('abc',{scene:photo},{scene:'camera'},{scene:'2026-11-27T12:00:00Z'});
  expect(fetcher).toHaveBeenCalledTimes(2);
  const calls=fetcher.mock.calls;expect(calls.map(call=>(call[1].body as Blob).size)).toEqual([512*1024,700000-512*1024]);
  expect(calls[0][1].headers['X-Photo-Source']).toBe('camera');expect(calls[0][1].headers['X-Captured-At']).toBe('2026-11-27T12:00:00Z');
  expect(calls[0][1].headers['X-Photo-SHA256']).toMatch(/^[0-9a-f]{64}$/);
  expect(new Uint8Array(await new Blob(calls.map(call=>call[1].body)).arrayBuffer())).toEqual(new Uint8Array(await photo.arrayBuffer()));
 });
 it('requests analysis of saved originals without reuploading them',async()=>{const fetcher=vi.fn().mockResolvedValue(new Response('{}',{status:200}));vi.stubGlobal('fetch',fetcher);await api.analyzeSaved('abc');expect(fetcher.mock.calls[0][0]).toBe('/api/reports/abc/analyze');expect(fetcher.mock.calls[0][1].body).toBeUndefined();});
 it('turns inaccessible network into a recoverable message',async()=>{vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('network')));await expect(api.list()).rejects.toThrow('Нет связи');});
 it('exposes server access errors without inventing a successful result',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:{code:'NOT_FOUND',message:'Материалы не найдены'}}),{status:404})));await expect(api.get('private')).rejects.toThrow('Материалы не найдены');});
 it('explains an HTML proxy size rejection during photo upload',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('<html>Request Entity Too Large</html>',{status:413,headers:{'Content-Type':'text/html'}})));await expect(api.upload('abc',{scene:new Blob(['photo'],{type:'image/jpeg'})})).rejects.toThrow('Сервер отклонил размер фотографий');});
});
