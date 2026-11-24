import type { Analysis, Draft, Kind, Report } from './types';
export interface CameraPreview {width:number;height:number;quality:{warnings:string[]};boxes:{label:string;kind:'plate'|'sign';bbox:number[]}[];plate_available:boolean;sign_available:boolean|null}
async function request<T>(path:string,init:RequestInit={}):Promise<T>{
  const controller=new AbortController(); const timer=setTimeout(()=>controller.abort(),90000);
  try {const response=await fetch(`/api${path}`,{...init,credentials:'include',signal:init.signal||controller.signal});
    if(!response.ok){const body=await response.json().catch(()=>null);throw new Error(body?.error?.message||'Не удалось сохранить данные. Попробуйте ещё раз.');}
    return response.json() as Promise<T>;
  }catch(error){if(error instanceof DOMException&&error.name==='AbortError')throw new Error('Проверка заняла слишком много времени. Повторите попытку или проверьте данные сами.',{cause:error});if(error instanceof TypeError)throw new Error('Нет связи. Фотографии сохранены на устройстве — попробуйте ещё раз.',{cause:error});throw error;}finally{clearTimeout(timer);}
}
const json=(method:string,body:unknown):RequestInit=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
function editable(data:Partial<Draft>){const {id,created_at,updated_at,photos,creation_key,...fields}=data;void id;void created_at;void updated_at;void photos;void creation_key;return fields;}
let sessionBootstrap:Promise<unknown>|null=null;
function ensureSession(){if(!sessionBootstrap)sessionBootstrap=request('/health').catch(error=>{sessionBootstrap=null;throw error;});return sessionBootstrap;}
export const api={
 cameraPreview:async(kind:Kind,frame:Blob,signal?:AbortSignal):Promise<CameraPreview>=>{const body=new FormData();body.append('kind',kind);body.append('frame',frame,'preview.jpg');const response=await fetch('/api/camera-preview',{method:'POST',body,credentials:'include',signal});if(!response.ok)throw new Error('Подсказки камеры временно недоступны.');return response.json();},
 mapConfig:()=>request<{yandex_js_key:string}>('/map-config'),
 list:()=>request<Report[]>('/reports'), get:(id:string)=>request<Report>(`/reports/${encodeURIComponent(id)}`),
 create:async(data:Draft)=>{await ensureSession();const init=json('POST',editable(data));if(data.creation_key)init.headers={...init.headers,'Idempotency-Key':data.creation_key};return request<Report>('/reports',init);}, update:(id:string,data:Partial<Draft>)=>request<Report>(`/reports/${encodeURIComponent(id)}`,json('PATCH',editable(data))),
 remove:(id:string)=>request<{ok:boolean}>(`/reports/${encodeURIComponent(id)}`,{method:'DELETE'}),
 upload:(id:string,files:Partial<Record<Kind,Blob>>,sources:Partial<Record<Kind,'camera'|'upload'>>={},capturedAt:Partial<Record<Kind,string>>={})=>{const body=new FormData();Object.entries(files).forEach(([kind,blob])=>{if(blob){body.append(`${kind}_photo`,blob,`${kind}.${blob.type==='image/png'?'png':blob.type==='image/webp'?'webp':'jpg'}`);body.append(`${kind}_source`,sources[kind as Kind]||'upload');if(sources[kind as Kind]==='camera'&&capturedAt[kind as Kind])body.append(`${kind}_captured_at`,capturedAt[kind as Kind]!);}});return request<Report>(`/reports/${encodeURIComponent(id)}/photos`,{method:'POST',body});},
 analyze:(files:Partial<Record<Kind,Blob>>)=>{const body=new FormData();Object.entries(files).forEach(([kind,blob])=>{if(blob)body.append(`${kind}_photo`,blob,`${kind}.jpg`);});return request<Analysis>('/analyze',{method:'POST',body});},
 geocode:(latitude:number,longitude:number,consent=false)=>request<{address:string|null;source:string;needs_manual:boolean;reason?:string}>('/geocode/reverse',json('POST',{latitude,longitude,consent,provider:consent?'nominatim':undefined})),
 photo:(id:string,kind:Kind)=>`/api/reports/${encodeURIComponent(id)}/photos/${kind}`,
 async export(id:string){const response=await fetch(`/api/reports/${encodeURIComponent(id)}/export`,{credentials:'include'});if(!response.ok)throw new Error('Не удалось скачать пакет. Повторите попытку.');return response.blob();}
};
