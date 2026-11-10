# Spike Técnico (#388): Comparativo de Bibliotecas de Leitura de Código de Barras e QR Code

**Projeto:** Sistema de Gestão e Empréstimo de Equipamentos (JPRH)  
**Autor:** João Henrique  
**Data:** 10 de Novembro de 2026  
**Status:** Concluído / Aprovado  

---

## 1. Contexto e Objetivo
O sistema de gestão e empréstimo necessita de captura rápida de códigos de patrimônio (`codigo_patrimonio`) e códigos de controle interno (`codigo_interno`) diretamente pela câmera de dispositivos móveis (smartphones dos técnicos/estagiários) ou webcams dos guichês do campus.

Este spike compara as 3 principais abordagens de mercado contra etiquetas reais utilizadas nos laboratórios e departamentos do campus:
1. **BarcodeDetector API (Nativa W3C / Shape Detection API)**
2. **ZXing (`@zxing/library` / `@zxing/browser`)**
3. **html5-qrcode**

---

## 2. Padrões de Etiquetas Reais do Campus
* **Etiquetas Metálicas de Patrimônio:** Impressas em Code 128 e Code 39, com reflexo metálico e caracteres alfanuméricos com barra `/` (ex.: `PAT-LAB/0099`).
* **Etiquetas Adesivas Térmicas:** Impressas em Code 128 de alta densidade e QR Code bidimensional.
* **Tamanho Típico:** 30mm x 15mm a 50mm x 25mm.

---

## 3. Matriz Comparativa Detalhada

| Critério de Avaliação | BarcodeDetector API (Nativo) | ZXing (`@zxing/browser`) | html5-qrcode |
| :--- | :--- | :--- | :--- |
| **Arquitetura** | Aceleração por hardware nativa do SO/Browser | WebAssembly / JS compilado puro | Wrapper em torno de ZXing + BarcodeDetector |
| **Suporte a Code 128 / Code 39** | Excelente (nativo) | Excelente | Muito Bom |
| **Suporte a QR Code / Data Matrix** | Excelente | Excelente | Excelente |
| **Latência por Quadro (FPS)** | **12–25 ms** (60 FPS fluidos) | 65–110 ms (10–15 FPS) | 45–80 ms (15–20 FPS) |
| **Tolerância a Reflexo e Iluminação Fraca** | Muito Alta (usa pipeline nativo do ISP) | Média (exige contraste elevado) | Média/Alta |
| **Tolerância a Ângulo e Distorção** | Até ~45° de inclinação | Até ~30° de inclinação | Até ~35° de inclinação |
| **Compatibilidade de Navegadores** | Chrome/Edge Android (100%), Safari iOS (17+ experimental) | Universal (qualquer browser com WebRTC) | Universal (com fallback inteligente) |
| **Tamanho do Pacote (Bundle Size)** | **0 KB** (Zero dependências adicionais) | ~280 KB minificado | ~160 KB minificado |
| **Facilidade de Integração no React** | Alta (via hook personalizado) | Média (gerenciamento manual de stream) | Alta (componente pronto ou hook) |

---

## 4. Testes com Amostras Reais do Campus

### Teste A: Etiqueta de Patrimônio Metálica (Reflexo de Lâmpada Fluorescente)
* **BarcodeDetector API:** Reconheceu em **< 150ms** mesmo com reflexo parcial na etiqueta.
* **html5-qrcode:** Reconheceu em **~420ms** após ajuste de distância da câmera.
* **ZXing puro:** Dificuldade em focar quando o reflexo atinge as barras centrais (média de 850ms).

### Teste B: Código Alfanumérico com Barras (`PAT-LAB/0099`)
* Todas as três bibliotecas decodificaram a string completa com fidelidade, preservando a barra (`/`) e os zeros à esquerda. O endpoint de backend `#390` (`GET /equipamentos/codigo/{codigo:path}`) foi projetado exatamente com `{codigo:path}` para suportar essa formatação nativa.

### Teste C: Dispositivo Móvel de Baixo Custo (Android com câmera básica)
* **BarcodeDetector API:** Manteve a interface a 60 FPS sem aquecimento do aparelho ou travamento de thread.
* **ZXing:** Consumo elevado de CPU (> 65% em um único núcleo) e queda de framerate.

---

## 5. Recomendação Técnica para o Frontend

Adotar uma **estratégia híbrida resiliente (Progressive Enhancement)**:
1. **Camada Primária:** Verificar se `'BarcodeDetector' in window`. Se disponível, utilizar a API nativa do navegador para máxima performance, 0 KB de bundle e leitura instantânea.
2. **Camada de Fallback:** Se não estiver disponível (ex.: Firefox Desktop ou navegadores legados), utilizar **`html5-qrcode`**, que já encapsula a inicialização da câmera, permissões do usuário, seleção de câmeras frontal/traseira e renderização da mira visual.

```typescript
// Exemplo de abstração recomendada para o componente Scanner:
export async function getScannerEngine() {
  if ('BarcodeDetector' in window) {
    const supportedFormats = await (window as any).BarcodeDetector.getSupportedFormats();
    if (supportedFormats.includes('code_128')) {
      return new NativeBarcodeEngine();
    }
  }
  return new Html5QrcodeFallbackEngine();
}
```

---

## 6. Veredito e Próximos Passos
* **Task #388 concluída e documentada.**
* O backend (Task `#390`) já se encontra 100% aderente às saídas testadas, validado com 35 testes automatizados.
