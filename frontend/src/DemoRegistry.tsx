import {Database} from 'lucide-react';
import {demoVehicles,lookupDemoVehicle} from './registryFixtures';
import s from './App.module.css';
export default function DemoRegistry({plate}:{plate:string}){
 const found=lookupDemoVehicle(plate);
 return <section className={s.demoRegistry} aria-label="Демонстрационная база автомобилей">
 <h3><Database size={20}/> Проверка по демобазе</h3>
 <p role="status">{!plate?'Сверьте номер на двух фото, чтобы проверить его по базе.':found?'Номер найден в демонстрационной базе автомобилей для парковки на местах для инвалидов.':'Номер не найден в демонстрационной базе автомобилей для парковки на местах для инвалидов.'}</p>
 <p>Это учебная база с вымышленными данными, без связи с государственными реестрами. Результат не подтверждает право на парковку или нарушение. Создать обращение можно в любом случае.</p>
 <details><summary>Посмотреть примеры записей</summary><p>Все ФИО и идентификаторы ниже вымышлены.</p>{demoVehicles.map(vehicle=><dl key={vehicle.plate} className={s.demoVehicle}><dt>Госномер</dt><dd>{vehicle.plate}</dd><dt>Автомобиль</dt><dd>{vehicle.car}</dd><dt>ФИО</dt><dd>{vehicle.name}</dd><dt>VIN (пример)</dt><dd>{vehicle.vin}</dd><dt>Водительское удостоверение (пример)</dt><dd>{vehicle.licence}</dd></dl>)}</details>
 </section>;
}
