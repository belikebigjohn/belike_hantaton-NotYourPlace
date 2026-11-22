export function latinPlateValue(value:string):string{
 const ru='АВЕКМНОРСТУХ',latin='ABEKMHOPCTYX';
 return value.toUpperCase().replace(/[АВЕКМНОРСТУХ]/g,c=>latin[ru.indexOf(c)]).replace(/[^ABCEHKMOPTXY0-9]/g,'');
}
export function isRussianPlate(value:string):boolean{return /^[ABCEHKMOPTXYАВЕКМНОРСТУХ]\d{3}[ABCEHKMOPTXYАВЕКМНОРСТУХ]{2}\d{2,3}$/.test(value.toUpperCase().replace(/\s/g,''));}
export function plateParts(value:string){
 const text=latinPlateValue(value),match=text.match(/^([ABCEHKMOPTXY]?)(\d{0,3})([ABCEHKMOPTXY]{0,2})(\d{0,3})$/);
 return {letter:match?.[1]||'',digits:match?.[2]||'',suffix:match?.[3]||'',region:match?.[4]||''};
}
