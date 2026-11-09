---
name: editar-video
description: Conduz a edição de um vídeo no Legend AI Edit, do bruto da câmera ao 4K final, uma etapa aprovada por vez (preparação, plano de corte, rascunho, acabamento com motions, final) e abre o editor de linha do tempo. Use quando a pessoa pedir para editar, continuar, ajustar ou renderizar um vídeo desta pasta.
---

# Editar um vídeo

Leia antes:
- `CLAUDE.md`, que aponta as regras;
- `CLAUDE.local.md`, que aponta a memória pessoal em `.memoria/MEMORIA.md`;
- o estilo do canal em `estilos/<canal>.md`.

## Onde estamos

1. Ache o vídeo: o que a pessoa disse, ou a pasta mais recente em `videos/`. Leia `trabalho/projeto.yml` se existir.
2. Descubra a etapa pelo que já existe na pasta:

| Existe em `trabalho/` | Próxima etapa | Guia |
| --- | --- | --- |
| nada (só `bruto/`) | preparação | `docs/etapas/preparacao.md` |
| `transcricao/`, sem `plano_v*.md` aprovado | plano de corte | `docs/etapas/plano-de-corte.md` |
| plano aprovado, sem rascunho aprovado | rascunho | `docs/etapas/rascunho.md` |
| rascunho aprovado | acabamento (com motion: `docs/etapas/motion.md`) | `docs/etapas/acabamento.md` |
| acabamento aprovado | final 4K (`finish.py --source bruto`) | `docs/etapas/acabamento.md` |
| `timeline_v*.json` mais nova que o último render | a pessoa editou à mão: parta dela | `docs/etapas/linha-do-tempo.md` |

3. Diga em uma frase onde o vídeo está e qual é a próxima etapa.

## Como trabalhar

- Uma etapa por vez. Mostre o resultado (prévia, plano em texto, quadros) e espere o "sim" antes da próxima.
- Grave a aprovação em `trabalho/projeto.yml`.
- Nunca sobrescreva: todo script gera a próxima versão livre.
- Conferência mínima de cada render:
  - contagem de quadros;
  - duração do áudio;
  - texto (transcreva o resultado);
  - loudness;
  - um ou dois quadros dos pontos com efeito.
- Pedidos de ajuste viram uma nova versão, nunca uma edição em cima da anterior.
- Correção que vale para outros vídeos vira uma linha em `aprendizados.md`. Gosto aprovado vai para `estilos/<canal>.md`, e preferência pessoal para `.memoria/MEMORIA.md`.
- Para a pessoa ajustar sozinha, ofereça o editor: `scripts/editor.sh`.

## Downloads e instalações

Música e efeitos sonoros do Epidemic Sound: mostre as prévias (`lqmp3Url`) e baixe só com o "sim":
- música em `videos/<pasta>/assets/`;
- efeito sonoro em `sfx/<tipo>/`, com uma linha em `sfx/INDEX.md`.

Instalar qualquer coisa nova também pede o "sim".
