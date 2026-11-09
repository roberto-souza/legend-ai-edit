# Motion graphics (HyperFrames)

As animações ficam em `motion/<modelo>/`, um projeto do HyperFrames por modelo (HTML, CSS e GSAP). O texto entra por variáveis. A versão do HyperFrames é fixa em `motion/package.json` (0.9.26).

- **Render:** o `scripts/motion.py` gera ProRes 4444 com transparência a 29,97 fps, em 1080p (prévia) ou 4K (final). O arquivo vai para `trabalho/motion/`, com cache por modelo, texto e resolução; mudar o modelo invalida o cache.
- **No vídeo:** o `finish.py` sobrepõe cada render no início do corte. Modelos:
  - `titulo`: título de bloco no alto, à esquerda, com o selo de `titulo_selo`;
  - `nome`: nome na tela embaixo, à esquerda, acima da legenda. No campo `nome` do corte, use "Nome | função".

  Os dois aparecem no inspetor do editor. Sem o HyperFrames instalado, o título vira texto simples no alto.
- **Modelo novo:** copie `motion/titulo/` e declare as variáveis em `data-composition-variables`. Duração `(N − 0,5) / fps`. Depois:
  1. rode `npx hyperframes check` dentro da pasta até não sobrar erro (o aviso de primeiro quadro vazio é esperado);
  2. renderize um teste com `scripts/motion.py` e confira os quadros.
- **Armadilhas:** veja o guia do LeiteZ/fluxo-de-edicao (`guias/hyperframes.md`). As que já pegaram aqui:
  - espaçamento entre palavras em `px`, não em `em` de contêiner;
  - máscara com folga para acento e cedilha;
  - `fromTo` com `lazy: false`.
- **Estilo:** nada de texto grande no centro da tela. Títulos ficam no terço de cima, à esquerda, longe da legenda e do rosto.
