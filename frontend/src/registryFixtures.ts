import {latinPlateValue,isRussianPlate} from './plateFormat';
// Demo-only records. Associated people and identifiers are fictitious; no official registry data.
export const demoVehicles=[
 {plate:'A123BC77',vin:'TEST0000000000001',name:'Алексей Примеров',licence:'00 00 000001',car:'Lada Vesta'},
 {plate:'M456HO199',vin:'TEST0000000000002',name:'Марина Образцова',licence:'00 00 000002',car:'Renault Logan'},
 {plate:'E300EY763',vin:'TEST0000000000003',name:'Павел Макетов',licence:'00 00 000003',car:'Kia Rio'},
 {plate:'H539BK186',vin:'TEST0000000000004',name:'Тестовый Водитель',licence:'00 00 000004',car:'Тестовый автомобиль'},
];
export function lookupDemoVehicle(plate:string){return isRussianPlate(plate)?demoVehicles.find(vehicle=>vehicle.plate===latinPlateValue(plate)):undefined;}
export function registryStatement(plate:string):string{
 if(!isRussianPlate(plate))return '';
 return `По результатам автоматической проверки системы автомобиль с указанным государственным регистрационным номером ${lookupDemoVehicle(plate)?'найден':'не найден'} в демонстрационной базе автомобилей для парковки на местах для инвалидов. Проверка по государственным реестрам не проводилась.`;
}
