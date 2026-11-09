# Regras de edição

- Mídia do usuário nunca é movida, renomeada nem apagada; o que o Claude gera fica em `trabalho/` e `final/`.
- Entregas versionadas (`_v01`, `_v02`); nunca sobrescrever um render.
- Uma etapa por vez; cada etapa parte da anterior aprovada; nada de encadear sozinho.
- O Claude decide sobre o texto; os scripts calculam tempo, frames, bordas e níveis.
- Conversão segundo → frame numa função só, com a taxa real do material (29,97 ≠ 30).
- Entrega final em 4K; preview e rascunho a partir de proxies; teto de zoom vem do estilo do projeto.
- Gosto mora em `estilos/<projeto>.md`; ofício mora nas skills.
- Correção que vale para outros vídeos vira linha em `aprendizados.md`; as skills só mudam quando o usuário pedir.
- Commit convencional com emoji do `git-cz`, em português.
