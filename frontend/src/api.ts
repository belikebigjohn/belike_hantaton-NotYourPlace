import type { Analysis, Draft, Kind, Report } from './types';
import {getMaxInitData} from './messenger/maxAdapter';
export class ApiError extends Error {constructor(message:string,public status:number){super(message);}}
function authHeaders(headers?:HeadersInit):Record<string,string> {const result=headers instanceof Headers?Object.fromEntries(headers.entries()):Array.isArray(headers)?Object.fromEntries(headers):{...headers};const initData=getMaxInitData();if(initData)result['X-Max-Init-Data']=initData;return result;}
export interface CameraPreview {width:number;height:number;quality:{warnings:string[]};boxes:{label:string;kind:'plate'|'sign';bbox:number[]}[];plate_available:boolean;sign_available:boolean|null}
async function request<T>(path:string,init:RequestInit={}):Promise<T>{
  const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),90000);
  try {const response=await fetch(`/api${path}`,{...init,headers:authHeaders(init.headers),credentials:'include',signal:init.signal||controller.signal});
    if(!response.ok){const body=await response.json().catch(()=>null);const fallback=response.status===413?'Сервер отклонил размер фотографий. Они остались в черновике на устройстве. Администратору нужно увеличить лимит загрузки прокси.':response.status===502||response.status===503||response.status===504?'Сервер временно недоступен. Фотографии остались на устройстве — повторите попытку позже.':'Не удалось сохранить данные. Попробуйте ещё раз.';throw new ApiError(body?.error?.message||fallback,response.status);}
    return response.json() as Promise<T>;
  }catch(error){if(error instanceof DOMException&&error.name==='AbortError')throw new Error('Проверка заняла слишком много времени. Повторите попытку или проверьте данные сами.',{cause:error});if(error instanceof TypeError)throw new Error('Нет связи. Фотографии сохранены на устройстве — попробуйте ещё раз.',{cause:error});throw error;}finally{clearTimeout(timer);}
}
const json=(method:string,body:unknown):RequestInit=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const photoChunkSize=512*1024;
async function photoHash(blob:Blob){const bytes=new Uint8Array(await crypto.subtle.digest('SHA-256',await blob.arrayBuffer()));return [...bytes].map(value=>value.toString(16).padStart(2,'0')).join('');}
function editable(data:Partial<Draft>){const {id,created_at,updated_at,photos,creation_key,...fields}=data;void id;void created_at;void updated_at;void photos;void creation_key;return fields;}
let sessionBootstrap:Promise<unknown>|null=null;
function ensureSession(){if(!sessionBootstrap)sessionBootstrap=request('/health').catch(error=>{sessionBootstrap=null;throw error;});return sessionBootstrap;}
export const api={
 cameraPreview:async(kind:Kind,frame:Blob,signal?:AbortSignal):Promise<CameraPreview>=>{const body=new FormData();body.append('kind',kind);body.append('frame',frame,'preview.jpg');const response=await fetch('/api/camera-preview',{method:'POST',body,headers:authHeaders(),credentials:'include',signal});if(!response.ok)throw new Error('Подсказки камеры временно недоступны.');return response.json();},
 mapConfig:()=>request<{yandex_js_key:string}>('/map-config'),
 list:()=>request<Report[]>('/reports'), get:(id:string)=>request<Report>(`/reports/${encodeURIComponent(id)}`),
 create:async(data:Draft)=>{await ensureSession();const init=json('POST',editable(data));if(data.creation_key)init.headers={...init.headers,'Idempotency-Key':data.creation_key};return request<Report>('/reports',init);}, update:(id:string,data:Partial<Draft>)=>request<Report>(`/reports/${encodeURIComponent(id)}`,json('PATCH',editable(data))),
 remove:(id:string)=>request<{ok:boolean}>(`/reports/${encodeURIComponent(id)}`,{method:'DELETE'}),
 upload:async(id:string,files:Partial<Record<Kind,Blob>>,sources:Partial<Record<Kind,'camera'|'upload'>>={},capturedAt:Partial<Record<Kind,string>>={}):Promise<Report>=>{let report:Report|undefined;for(const kind of ['scene','plate'] as Kind[]){const blob=files[kind];if(!blob)continue;const uploadId=crypto.randomUUID(),hash=await photoHash(blob),count=Math.ceil(blob.size/photoChunkSize);for(let index=0;index<count;index++){const response=await request<Report|{received:number}>(`/reports/${encodeURIComponent(id)}/photo-chunks/${kind}/${uploadId}/${index}`,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Chunk-Count':String(count),'X-Photo-Size':String(blob.size),'X-Photo-SHA256':hash,'X-Photo-Source':sources[kind]||'upload',...(sources[kind]==='camera'&&capturedAt[kind]?{'X-Captured-At':capturedAt[kind]}:{})},body:blob.slice(index*photoChunkSize,Math.min((index+1)*photoChunkSize,blob.size))});if(index===count-1)report=response as Report;}}if(!report)throw new Error('Выберите фотографию для сохранения.');return report;},
 analyze:(files:Partial<Record<Kind,Blob>>)=>{const body=new FormData();Object.entries(files).forEach(([kind,blob])=>{if(blob)body.append(`${kind}_photo`,blob,`${kind}.jpg`);});return request<Analysis>('/analyze',{method:'POST',body});},
 analyzeSaved:(id:string)=>request<Analysis>(`/reports/${encodeURIComponent(id)}/analyze`,{method:'POST'}),
 geocode:(latitude:number,longitude:number,consent=false)=>request<{address:string|null;source:string;needs_manual:boolean;reason?:string}>('/geocode/reverse',json('POST',{latitude,longitude,consent,provider:consent?'nominatim':undefined})),
 photo:(id:string,kind:Kind)=>`/api/reports/${encodeURIComponent(id)}/photos/${kind}`,
 async photoBlob(id:string,kind:Kind){const response=await fetch(api.photo(id,kind),{headers:authHeaders(),credentials:'include'});if(!response.ok)throw new ApiError('Не удалось открыть фотографию.',response.status);return response.blob();},
 sendMax:(id:string)=>request<{delivered:boolean}>(`/reports/${encodeURIComponent(id)}/send-max`,{method:'POST'}),
 async export(id:string){const response=await fetch(`/api/reports/${encodeURIComponent(id)}/export`,{headers:authHeaders(),credentials:'include'});if(!response.ok)throw new Error('Не удалось скачать пакет. Повторите попытку.');return response.blob();}
};
