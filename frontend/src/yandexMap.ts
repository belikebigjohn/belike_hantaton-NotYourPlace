export type MapPoint=[number,number];
export function validMapPoint(latitude:unknown,longitude:unknown):MapPoint|null{
 if(!['number','string'].includes(typeof latitude)||!['number','string'].includes(typeof longitude)||String(latitude).trim()===''||String(longitude).trim()==='')return null;
 const lat=Number(latitude),lon=Number(longitude);
 return Number.isFinite(lat)&&Number.isFinite(lon)&&Math.abs(lat)<=90&&Math.abs(lon)<=180?[lat,lon]:null;
}
export function widgetUrl(point:MapPoint|null){const [lat,lon]=point||[56.8389,60.6057];const query=new URLSearchParams({ll:`${lon},${lat}`,z:point?'17':'12',lang:'ru_RU'});if(point)query.set('pt',`${lon},${lat},pm2rdm`);return `https://yandex.ru/map-widget/v1/?${query}`;}
export interface YandexMark {geometry:{setCoordinates:(point:MapPoint)=>void;getCoordinates:()=>MapPoint};events:{add:(name:string,callback:()=>void)=>void}}
export interface YandexMap {geoObjects:{add:(mark:YandexMark)=>void};events:{add:(name:string,callback:(event:{get:(name:string)=>unknown})=>void)=>void};setCenter:(point:MapPoint,zoom?:number)=>void;destroy:()=>void}
export interface YandexGeo {geometry:{getCoordinates:()=>MapPoint};getAddressLine:()=>string}
export interface YandexSDK {ready:(callback:()=>void)=>void;Map:new(element:HTMLElement,state:Record<string,unknown>,options?:Record<string,unknown>)=>YandexMap;Placemark:new(point:MapPoint,properties?:Record<string,unknown>,options?:Record<string,unknown>)=>YandexMark;geocode:(query:string|MapPoint)=>Promise<{geoObjects:{get:(index:number)=>YandexGeo|undefined}}>}
declare global {interface Window {ymaps?:YandexSDK}}
let sdkPromise:Promise<YandexSDK>|null=null;
export function loadYandex(key:string):Promise<YandexSDK>{
 if(!key)return Promise.reject(new Error('Карта недоступна. Уточните адрес в поле ниже.'));
 if(!sdkPromise)sdkPromise=new Promise<YandexSDK>((resolve,reject)=>{
  const script=document.createElement('script');script.src=`https://api-maps.yandex.ru/2.1/?apikey=${encodeURIComponent(key)}&lang=ru_RU`;script.async=true;
  const timeout=setTimeout(()=>{script.remove();sdkPromise=null;reject(new Error('Не удалось загрузить карту. Попробуйте ещё раз.'));},15000);
  script.onload=()=>{if(window.ymaps)window.ymaps.ready(()=>{clearTimeout(timeout);resolve(window.ymaps!);});else{clearTimeout(timeout);sdkPromise=null;reject(new Error('Не удалось открыть карту.'));}};
  script.onerror=()=>{clearTimeout(timeout);script.remove();sdkPromise=null;reject(new Error('Нет связи с картой. Попробуйте ещё раз.'));};document.head.appendChild(script);
 });return sdkPromise;
}
