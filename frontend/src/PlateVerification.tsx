import type {CSSProperties} from 'react';
import {CheckCircle2,Info,RefreshCw} from 'lucide-react';
import type {Analysis,Kind,PlateCandidate} from './types';
import {photoLabels,plateColors,readableCandidates,reviewComparison,reviewValues,selectedPlateBox} from './analysisReview';
import PhotoPreview from './PhotoPreview';
import RussianPlateInput from './RussianPlateInput';
import {isRussianPlate} from './plateFormat';
import s from './App.module.css';
interface Props {analysis:Analysis|null;urls:Partial<Record<Kind,string>>;onEdit:(kind:Kind,value:string,candidate?:PlateCandidate)=>void;onRetake:(kind:Kind)=>void}
export default function PlateVerification({analysis,urls,onEdit,onRetake}:Props){
 const review=reviewValues(analysis),comparison=reviewComparison(analysis);
 return <section className={s.plateVerification} aria-label="Сверка номера на двух фотографиях">
 <div className={s.verificationIntro}><h2>Номер на двух фото</h2></div>
 {(['scene','plate'] as Kind[]).map(kind=>{
  const raw=analysis?.plates_by_photo?.[kind],value=kind==='scene'?review.scene_value:review.plate_value,candidates=readableCandidates(analysis,kind),box=selectedPlateBox(analysis,kind);
  const boxes=[...(kind==='scene'?(analysis?.signs||[]).map((sign,index)=>({bbox:sign.bbox,label:sign.class_code==='6.4'?'Парковка':sign.class_code==='8.17'?'Инвалиды':sign.class_code,color:'#ffffff',dashed:true,key:`sign-${index}`})):[]),...(box?[{bbox:box,label:kind==='scene'?'Номер · общий план':'Номер · крупный план',color:plateColors[kind],key:`plate-${kind}`}]:[])];
  return <article key={kind} className={s.platePhotoSection} style={{'--plate-color':plateColors[kind]} as CSSProperties}>
   <div className={s.platePhotoHeading}><span>{kind==='scene'?'1':'2'}</span><h3>{photoLabels[kind]}</h3><button onClick={()=>onRetake(kind)} aria-label={`Переснять: ${photoLabels[kind].toLowerCase()}`}><RefreshCw size={18}/></button></div>
   <div className={s.verificationPhoto}><PhotoPreview url={urls[kind]} alt={photoLabels[kind]} boxes={boxes}/></div>
   {raw?.value&&isRussianPlate(raw.value)?<p className={s.rawReading}>Распознано: <strong>{raw.value}</strong>{raw.confidence!=null&&<span> · оценка {Math.round(raw.confidence*100)}%</span>}</p>:<p className={s.rawReading}><Info size={16}/> {analysis?.plates_by_photo?'Номер не прочитан целиком. Введите его с фото или переснимите.':'Снимок ещё не проверен. Повторите распознавание или введите номер с фото.'}</p>}
   <RussianPlateInput label={kind==='scene'?'Номер на общем фото':'Номер на крупном фото'} value={value} onChange={value=>onEdit(kind,value)}/>
   {candidates.length>1&&<fieldset className={s.candidateList}><legend>Выберите нужный автомобиль</legend>{candidates.map((candidate,index)=><label key={`${candidate.value}-${index}`} className={s.candidate}><input type="radio" name={`candidate-${kind}`} checked={candidate.value===value&&candidate.bbox?.join(',')===box?.join(',')} onChange={()=>onEdit(kind,candidate.value,candidate)}/><span><strong>{candidate.value}</strong><small>{photoLabels[kind]} · вариант {index+1}</small></span></label>)}</fieldset>}
  </article>;
 })}
 <div className={`${s.comparison} ${comparison==='match'?s.comparisonMatch:comparison==='mismatch'?s.comparisonMismatch:''}`} role="status" aria-live="polite">{comparison==='match'?<CheckCircle2 size={24}/>:<Info size={24}/>}<div><strong>{comparison==='match'?'Номера на двух фото совпадают':comparison==='mismatch'?'Номера на фото различаются':'Проверьте номер на каждом фото'}</strong><p>{comparison==='match'?'Подтвердите, что на обоих снимках один автомобиль.':comparison==='mismatch'?'Выберите нужный автомобиль или исправьте чтение по снимку. Продолжить можно после совпадения номеров.':'Заполните оба поля. Если номер не читается, сделайте новый снимок.'}</p></div></div>
 </section>;
}
