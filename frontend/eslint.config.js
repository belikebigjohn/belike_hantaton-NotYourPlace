import js from '@eslint/js';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  { files: ['src/**/*.{ts,tsx}'], languageOptions: { globals: { window: 'readonly', document: 'readonly', navigator: 'readonly', indexedDB: 'readonly', fetch: 'readonly', crypto: 'readonly', URL: 'readonly', Blob: 'readonly', FormData: 'readonly', Response: 'readonly', AbortController: 'readonly', DOMException: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly', createImageBitmap: 'readonly', console: 'readonly' } } },
);
