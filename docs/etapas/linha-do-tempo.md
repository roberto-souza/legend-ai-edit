# Etapa 5: linha do tempo editável

Para o usuário fazer ajustes finos sozinho, depois do acabamento aprovado.

1. Suba o editor: `.venv/bin/python scripts/timeline_server.py videos/<pasta>` e abra http://127.0.0.1:8765. O servidor só atende em 127.0.0.1.
2. Na primeira vez, ele carrega o acabamento mais recente (`<pasta>_acabamento_vNN.edl.json`). Depois, carrega a `timeline_vNN.json` mais recente; as outras versões ficam no seletor.
3. O que dá para fazer no editor:
   - aparar as bordas;
   - mudar a ordem;
   - dividir (S);
   - apagar;
   - duplicar;
   - escolher o zoom de cada corte;
   - marcar um corte como b-roll sem som, ou com glitch e preto e branco;
   - mover a imagem de apoio;
   - inserir clipes da biblioteca.
   A trilha de áudio só mostra onde entram a música e os efeitos sonoros, que vêm de `acabamento_vNN.json`.
4. "Salvar" cria `trabalho/timeline_vNN.json`, sem sobrescrever nada. "Renderizar prévia" e "Renderizar 4K" rodam `finish.py` com essa linha do tempo e a mesma configuração de acabamento.
5. Quando o usuário pedir ajustes depois de editar, parta da `timeline_vNN.json` mais recente, não do plano. O zoom salvo nela é respeitado (`zoom_manual`).

A prévia no navegador é aproximada: zoom por CSS, preto e branco sem glitch, vertical sem o fundo desfocado e legenda indicativa. O render é a referência.
