import {useEffect,useRef,useState} from 'react';
import {MapPin,ExternalLink} from 'lucide-react';
import {api} from './api';
import {loadYandex,validMapPoint,widgetUrl} from './yandexMap';
import type {MapPoint,YandexMap,YandexMark,YandexSDK} from './yandexMap';
import s from './App.module.css';
import Disclosure from './Disclosure';
interface Props {latitude:number|null;longitude:number|null;address:string;onPoint:(point:MapPoint,address?:string)=>void}
export default function YandexLocation({latitude,longitude,address,onPoint}:Props){
 const [active,setActive]=useState(false),[key,setKey]=useState<string|null>(null),[message,setMessage]=useState(''),[ready,setReady]=useState(false);
 const [lat,setLat]=useState(latitude?.toString()||''),[lon,setLon]=useState(longitude?.toString()||'');
 const host=useRef<HTMLDivElement>(null),map=useRef<YandexMap|null>(null),mark=useRef<YandexMark|null>(null),sdk=useRef<YandexSDK|null>(null),generation=useRef(0),callback=useRef(onPoint);callback.current=onPoint;
 const point=validMapPoint(latitude,longitude),pointRef=useRef(point),pinAdded=useRef(false);pointRef.current=point;
 useEffect(()=>{++generation.current;},[address]);
 useEffect(()=>{let alive=true;api.mapConfig().then(config=>{if(alive)setKey(config.yandex_js_key);}).catch(()=>{if(alive)setKey('');});return()=>{alive=false;};},[]);
 useEffect(()=>{setLat(latitude?.toString()||'');setLon(longitude?.toString()||'');if(point){mark.current?.geometry.setCoordinates(point);if(map.current&&mark.current&&!pinAdded.current){map.current.geoObjects.add(mark.current);pinAdded.current=true;}map.current?.setCenter(point,17);}},[latitude,longitude]);
 async function selectPoint(value:MapPoint){
  callback.current(value);setMessage('Точка выбрана. Проверьте адрес.');const token=++generation.current;
  if(!sdk.current)return;
  try{const result=await sdk.current.geocode(value);if(token!==generation.current)return;const found=result.geoObjects.get(0);if(found){callback.current(value,found.getAddressLine());setMessage('Адрес найден. Проверьте его перед продолжением.');}}catch{if(token===generation.current)setMessage('Точка сохранена. Укажите адрес в поле ниже.');}
 }
 const selectRef=useRef(selectPoint);selectRef.current=selectPoint;
 useEffect(()=>{
  if(!active||!key||!host.current)return;let alive=true;setReady(false);setMessage('Загружаем карту…');
  loadYandex(key).then(client=>{if(!alive||!host.current)return;sdk.current=client;const center=pointRef.current||[56.8389,60.6057];const instance=new client.Map(host.current,{center,zoom:pointRef.current?17:12,controls:['zoomControl']});map.current=instance;
   const pin=new client.Placemark(center,{}, {draggable:true,preset:'islands#redDotIcon'});mark.current=pin;if(pointRef.current)instance.geoObjects.add(pin);
   pinAdded.current=!!pointRef.current;instance.events.add('click',event=>{const coordinates=event.get('coords') as MapPoint;const valid=validMapPoint(coordinates?.[0],coordinates?.[1]);if(!valid)return;pin.geometry.setCoordinates(valid);if(!pinAdded.current){instance.geoObjects.add(pin);pinAdded.current=true;}void selectRef.current(valid);});
   pin.events.add('dragend',()=>void selectRef.current(pin.geometry.getCoordinates()));setReady(true);setMessage('Нажмите на карту, чтобы выбрать точку, или перетащите метку.');
  }).catch(error=>{if(alive)setMessage(error instanceof Error?error.message:'Карта недоступна. Уточните адрес ниже.');});
  return()=>{alive=false;++generation.current;map.current?.destroy();map.current=null;mark.current=null;sdk.current=null;};
 },[active,key]);
 async function findAddress(){if(!sdk.current||!address.trim())return;const token=++generation.current;setMessage('Ищем адрес…');try{const result=await sdk.current.geocode(address);if(token!==generation.current)return;const found=result.geoObjects.get(0);if(!found){setMessage('Адрес не найден. Уточните адрес или выберите точку.');return;}const coords=found.geometry.getCoordinates();mark.current?.geometry.setCoordinates(coords);if(mark.current&&!pinAdded.current){map.current?.geoObjects.add(mark.current);pinAdded.current=true;}callback.current(coords,found.getAddressLine());map.current?.setCenter(coords,17);setMessage('Проверьте положение метки.');}catch{if(token===generation.current)setMessage('Не удалось найти адрес. Попробуйте уточнить его.');}}
 return <section className={s.locationMap} aria-label="Место на Яндекс Карте"><h2><MapPin size={22}/>Место на карте</h2>
 {!active?<><p>Проверьте место, где стоит автомобиль.</p><button className={s.secondary} onClick={()=>setActive(true)}>Открыть Яндекс Карту</button></>:<>
 {key===null?<p role="status">Открываем карту…</p>:key?<div ref={host} className={s.mapCanvas} aria-label="Выбор точки на карте"/>:<iframe className={s.mapCanvas} src={widgetUrl(point)} title="Яндекс Карта места наблюдения" loading="lazy" referrerPolicy="strict-origin-when-cross-origin"/>}
 <p role="status">{key?message:point?'На карте отмечены указанные координаты. Проверьте положение метки.':'Откройте нужный район на карте и укажите адрес ниже. Координаты можно уточнить вручную.'}</p>
 {key&&<button className={s.secondary} disabled={!ready||!address.trim()} onClick={()=>void findAddress()}>Найти адрес на карте</button>}
 <a className={s.historyLink} href={point?`https://yandex.ru/maps/?pt=${point[1]},${point[0]}&z=17`:`https://yandex.ru/maps/?text=${encodeURIComponent(address||'Екатеринбург')}`} target="_blank" rel="noopener noreferrer">Открыть в Яндекс Картах <ExternalLink size={18}/></a>
 <Disclosure title="Уточнить координаты"><label className={s.field}>Широта<input inputMode="decimal" value={lat} onChange={event=>setLat(event.target.value)}/></label><label className={s.field}>Долгота<input inputMode="decimal" value={lon} onChange={event=>setLon(event.target.value)}/></label><button className={s.secondary} onClick={()=>{const chosen=validMapPoint(lat.replace(',','.'),lon.replace(',','.'));if(!chosen){setMessage('Укажите корректные широту и долготу.');return;}void selectPoint(chosen);}}>Показать точку</button>{!key&&message&&<p role="status">{message}</p>}</Disclosure>
 </>}
 </section>;
}
