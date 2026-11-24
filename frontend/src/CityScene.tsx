const scenes = [
  {src: '/parking-autumn.webp', alt: 'Осенняя парковка со знаком места для людей с инвалидностью'},
  {src: '/parking-green.webp', alt: 'Зелёная городская парковка со знаком места для людей с инвалидностью'},
  {src: '/parking-spring.webp', alt: 'Весенняя парковка с цветущими деревьями и специальным местом'},
  {src: '/parking-winter.webp', alt: 'Зимняя парковка со знаком места для людей с инвалидностью'},
];

function nextSceneIndex(): number {
  try {
    const saved = sessionStorage.getItem('chuzhoe-home-scene');
    const previous = Number(saved);
    const index = saved === null
      ? Math.floor(Math.random() * scenes.length)
      : (Number.isInteger(previous) ? previous + 1 : 0) % scenes.length;
    sessionStorage.setItem('chuzhoe-home-scene', String(index));
    return index;
  } catch {
    return Math.floor(Math.random() * scenes.length);
  }
}

const scene = scenes[nextSceneIndex()];

export default function CityScene() {
  return <img src={scene.src} width="1200" height="800" alt={scene.alt} decoding="async" fetchPriority="high" />;
}
