import {useEffect,useRef,useState} from 'react';
import {Image as ImageIcon} from 'lucide-react';
import s from './App.module.css';
interface Props{url?:string;alt:string;boxes?:{bbox:number[];label:string;color?:string;dashed?:boolean}[]}
export default function PhotoPreview({url,alt,boxes=[]}:Props){
 const [size,setSize]=useState<[number,number]>([1,1]),[rendered,setRendered]=useState<[number,number]>([1,1]),image=useRef<HTMLImageElement>(null);
 useEffect(()=>{const element=image.current;if(!element)return;const observer=new ResizeObserver(()=>setRendered([element.clientWidth,element.clientHeight]));observer.observe(element);return()=>observer.disconnect();},[url]);
 const scale=Math.max(.001,Math.min(rendered[0]/size[0],rendered[1]/size[1]));
 return <>{url?<><img ref={image} src={url} alt={alt} onLoad={event=>{setSize([event.currentTarget.naturalWidth,event.currentTarget.naturalHeight]);setRendered([event.currentTarget.clientWidth,event.currentTarget.clientHeight]);}}/>{boxes.length>0&&size[0]>1&&<svg className={s.detectionOverlay} viewBox={`0 0 ${size[0]} ${size[1]}`} preserveAspectRatio="xMidYMid meet" aria-label="Области обнаруженных объектов">{boxes.map(({bbox,label,color='#ffe45e',dashed=false},i)=>{
  const text=label.startsWith('Номер')?'Номер':label,font=13/scale,pad=5/scale,labelWidth=Math.min(size[0],text.length*font*.58+pad*2),labelY=Math.max(font+pad,bbox[1]-pad),labelX=Math.min(Math.max(0,bbox[0]),size[0]-labelWidth);
  return <g key={i}><rect x={bbox[0]} y={bbox[1]} width={bbox[2]} height={bbox[3]} fill="none" stroke="#101421" strokeWidth="7" vectorEffect="non-scaling-stroke"/><rect x={bbox[0]} y={bbox[1]} width={bbox[2]} height={bbox[3]} fill="none" stroke={color} strokeWidth="3" vectorEffect="non-scaling-stroke" strokeDasharray={dashed?'8 5':undefined}/><rect x={labelX} y={labelY-font-pad} width={labelWidth} height={font+pad*2} rx={3/scale} fill="#101421"/><text x={labelX+pad} y={labelY} fill={color} fontSize={font} fontFamily="Arial,sans-serif" fontWeight="700">{text}</text><title>{label}</title></g>;
 })}</svg>}</>:<ImageIcon/>}</>;
}
