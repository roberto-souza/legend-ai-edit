# Estilo: vlog (exemplo)

Ponto de partida para o estilo de um canal. Copie para `estilos/<seu-canal>.md` e ajuste. Os estilos de canal ficam só na sua máquina (`.gitignore`); este exemplo é o único que vai para o repositório.

## Formato e tom

- Horizontal 16:9 para YouTube; entrega em 4K.
- Duração: a que o material pedir; sem alvo fixo.
- Tom de vlog: bastidor, momentos do dia e humor primeiro. Explicação só o mínimo para dar contexto.

## Corte

- Tirar frases abandonadas, falsos começos e repetições entre clipes. Interjeições e reações ("Bora!") ficam quando têm graça.
- Pausas de até 0,6 s no rascunho (`--max-pause 0.6`), para a fala respirar.
- Imagens de apoio (gravação de tela ou do ambiente) entram por cima da fala que fala delas.
- Clipe vertical num vídeo horizontal: o próprio clipe, ampliado e desfocado, vira o fundo, e o clipe nítido fica centralizado por cima.
- Imprevistos do dia (a internet caiu, algo quebrou): um glitch marca o momento, e o resto do take fica em preto e branco.
- B-roll sem fala: sequência curta com música, mostrando o que a pessoa faz. Quando o som do lugar importa (dança, aplauso), use `broll ... com som`; ele fica uns 10 dB abaixo da voz (`broll_som_db: -10`).
- Timelapse: b-roll longo de câmera fixa entra acelerado (`velocidade`), de 6 a 8 s, sem fala. Corte o começo e o fim em que a pessoa dá o play e o stop.
- Erro repetido (vários takes da mesma fala): contador "TENTATIVA N" no canto, o último terminando em "FOI!", com um som cômico grave a cada número.

## Imagem

- Zoom leve, no máximo 1,15× sobre o 4K, para disfarçar o corte seco no meio de uma fala. Mais que isso perde nitidez.
- Fusão de 0,4 s (`"transicao": "dissolve"`) em cada troca de trecho, para os cortes não ficarem secos.
- Fade para o preto no fim (`fade_saida_s: 2`).

## Som

- Trilha de fundo no vídeo inteiro, baixa sob a fala (abaixa sozinha) e mais alta onde não há fala. Nível: -24 LUFS (`nivel_lufs`). Fica muda nos trechos de imprevisto em preto e branco.
- Música e efeitos sonoros do Epidemic Sound; confirme se o plano cobre o uso no canal.
- Efeito sonoro precisa ser audível: o pico cai no corte (`antes_s`).

## Texto na tela

- Legenda: branca, 5% da altura do quadro, borda preta fina, embaixo, com a palavra falada destacada em cor (`legenda_destaque`).
- Títulos de bloco: animados no HyperFrames, no terço de cima, à esquerda, com whoosh leve na entrada. Nunca texto grande no meio da tela.
- Nome na tela: só o nome, embaixo, à esquerda, acima da legenda.
- Nomes próprios na legenda: liste em `nomes_proprios`.

## Identidade do canal (preencha)

- Cores, fonte e logo do canal. Para títulos e nomes com a sua marca, copie `motion/titulo` e `motion/nome` para `motion/titulo-<canal>` e `motion/nome-<canal>` (também ficam fora do git) e escolha-os com `modelo_titulo` e `modelo_nome`.
- Música preferida (gênero, exemplos de faixas).
- Selo acima do título (`titulo_selo`), se não usar logo.
