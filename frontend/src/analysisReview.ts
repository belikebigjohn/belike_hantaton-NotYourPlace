import type {Analysis,Kind,PlateCandidate,PlateReview} from './types';
import {isRussianPlate} from './plateFormat';

export const photoLabels:Record<Kind,string>={scene:'Общий план',plate:'Крупный план номера'};
export const plateColors:Record<Kind,string>={scene:'#ffe45e',plate:'#ff76d5'};
export function normalizePlateValue(value:string):string{
 const latin='ABEKMHOPCTYX',cyrillic='АВЕКМНОРСТУХ';
 return value.toUpperCase().replace(/[^A-ZА-Я0-9]/g,'').replace(/[ABEKMHOPCTYX]/g,letter=>cyrillic[latin.indexOf(letter)]);
}
export function readableCandidates(analysis:Analysis|null,kind?:Kind):PlateCandidate[]{
 const values=kind?analysis?.plates_by_photo?.[kind]?.candidates:analysis?.plate.candidates;
 return (values||[]).filter(candidate=>isRussianPlate(candidate.value||''));
}
export function reviewValues(analysis:Analysis|null):PlateReview{
 return analysis?.plate_review||{scene_value:analysis?.plates_by_photo?.scene?.value||'',plate_value:analysis?.plates_by_photo?.plate?.value||'',confirmed:false};
}
export function reviewComparison(analysis:Analysis|null):'match'|'mismatch'|'needs_review'{
 const review=reviewValues(analysis),scene=normalizePlateValue(review.scene_value),plate=normalizePlateValue(review.plate_value);
 if(!isRussianPlate(scene)||!isRussianPlate(plate))return 'needs_review';
 return scene===plate?'match':'mismatch';
}
export function emptyAnalysis():Analysis{return {plate:{value:'',confidence:null,bbox:null,needs_review:true,candidates:[]},signs:[],parking_accessibility_evidence:'unknown',explanations:[],model_versions:{}};}
export function editReview(analysis:Analysis|null,kind:Kind,value:string,candidate?:PlateCandidate):Analysis{
 const original=analysis||emptyAnalysis(),review=reviewValues(original);
 return {...original,plate_review:{...review,[`${kind}_value`]:value,confirmed:false,selected_candidates:candidate?{...review.selected_candidates,[kind]:candidate}:review.selected_candidates}};
}
export function confirmReview(analysis:Analysis|null,confirmed:boolean):Analysis{
 const original=analysis||emptyAnalysis();
 return {...original,plate_review:{...reviewValues(original),confirmed:confirmed&&reviewComparison(original)==='match'}};
}
export function selectedPlateBox(analysis:Analysis|null,kind:Kind):number[]|null{
 return analysis?.plate_review?.selected_candidates?.[kind]?.bbox||analysis?.plates_by_photo?.[kind]?.bbox||null;
}

export function qualityHints(analysis:Analysis|null):{kind:Kind;label:string;warnings:string[]}[]{
 return (['scene','plate'] as Kind[]).flatMap(kind=>{
  const warnings=analysis?.quality?.[kind]?.warnings?.filter(value=>value.trim())||[];
  return warnings.length?[{kind,label:photoLabels[kind],warnings:[...new Set(warnings)]}]:[];
 });
}
export function signStatusText(state:Analysis['parking_accessibility_evidence']|undefined):string{
 return state==='detected'?'Знак «Парковка» с табличкой «Инвалиды» найден':state==='not_detected'?'Знак «Парковка» с табличкой «Инвалиды» не найден на общем фото':'Проверьте знак «Парковка» и табличку «Инвалиды» на общем фото';
}
