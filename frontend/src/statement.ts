import type {Draft} from './types';
import {registryStatement} from './registryFixtures';
export function statementForDraft(data:Draft):string{
 const date=new Intl.DateTimeFormat('ru-RU',{dateStyle:'medium',timeStyle:'short'}).format(new Date(data.observed_at));
 const paragraphs=[`Прошу проверить обстоятельства парковки автомобиля с государственным регистрационным номером ${data.plate} по адресу: ${data.address}.`,`Дата и время наблюдения: ${date}.\nНа месте парковки наблюдалось: ${data.designation}.`];
 if(data.analysis?.plate_review?.disability_sign_not_visible)paragraphs.push('При осмотре автомобиля опознавательный знак «Инвалид» мне не был виден. Прошу проверить наличие знака и соблюдение условий использования специального парковочного места.');
 if(data.observation)paragraphs.push(`Дополнительные обстоятельства: ${data.observation}`);
 const registry=registryStatement(data.plate);if(registry)paragraphs.push(registry);
 paragraphs.push('Сведения о праве пользователя автомобиля на парковку мне неизвестны. Прошу проверить изложенные обстоятельства и сообщить о результатах по указанному адресу для ответа.');
 return paragraphs.join('\n\n')+'\n';
}
