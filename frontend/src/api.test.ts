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
 it('preserves photograph bytes and explicitly sends capture source',async()=>{
  const fetcher=vi.fn().mockResolvedValue(new Response('{}',{status:200}));vi.stubGlobal('fetch',fetcher);const photo=new Blob([new Uint8Array([255,216,255,217])],{type:'image/jpeg'});
  await api.upload('abc',{scene:photo},{scene:'camera'});const body=fetcher.mock.calls[0][1].body as FormData;expect(body.get('scene_source')).toBe('camera');expect(await (body.get('scene_photo') as Blob).arrayBuffer()).toEqual(await photo.arrayBuffer());
 });
 it('turns inaccessible network into a recoverable message',async()=>{vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new TypeError('network')));await expect(api.list()).rejects.toThrow('Нет связи');});
 it('exposes server access errors without inventing a successful result',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({error:{code:'NOT_FOUND',message:'Материалы не найдены'}}),{status:404})));await expect(api.get('private')).rejects.toThrow('Материалы не найдены');});
 it('explains an HTML proxy size rejection during photo upload',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('<html>Request Entity Too Large</html>',{status:413,headers:{'Content-Type':'text/html'}})));await expect(api.upload('abc',{scene:new Blob(['photo'],{type:'image/jpeg'})})).rejects.toThrow('Сервер отклонил размер фотографий');});
});
