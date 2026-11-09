# Etapa 1: preparação

Entrada: brutos copiados em `videos/<data>_<nome>/bruto/`. Nada aqui altera os brutos.

1. Inventário: `.venv/bin/python scripts/inventory.py videos/<pasta>` cria `trabalho/inventario.json`. Confira a taxa de quadros: todas as contas usam a taxa real (`scripts/lae.py`, `seconds_to_frame`).
2. Proxies: `.venv/bin/python scripts/make_proxies.py videos/<pasta> --lut luts/<camera>.cube` cria `trabalho/proxies/<clipe>_proxy.mp4`. São 1080p H.264 com o LUT aplicado, com a mesma taxa e o mesmo número de quadros do bruto, e herdam o timecode. O script confere a contagem de quadros.
3. Transcrição: `.venv/bin/python scripts/transcribe.py videos/<pasta>` cria `trabalho/transcricao/<clipe>.json`. Cada palavra tem `start` e `end` em segundos, contados do início do clipe.

Os scripts pulam o que já existe e nunca sobrescrevem. Para refazer um arquivo, gere uma versão nova.

Saída para aprovação: resumo do inventário, um quadro de comparação D-Log e proxy, e o texto de cada clipe.
