export function getMessengerEnvironment(): 'max' | 'browser' {
  const host=window as Window & {WebApp?:unknown;MAX?:unknown};
  return host.MAX || (host.WebApp && /MAX/i.test(navigator.userAgent)) ? 'max' : 'browser';
}
