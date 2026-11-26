export function shouldDismissToastSwipe(dx:number,dy:number){
 return (Math.abs(dx)>=48&&Math.abs(dx)>Math.abs(dy)*1.2)||(dy<=-45&&Math.abs(dy)>Math.abs(dx)*1.2);
}
