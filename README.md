# media-triage

Skill de triagem de fotos e vídeos: separa o que vale manter de duplicadas, muito parecidas e sem qualidade — **sem nunca apagar os originais**.

Funciona em qualquer agente compatível com o padrão aberto de skills: **OpenCode, Claude Code, Gemini CLI, Codex, Cursor** e outros.

## O que faz

Dada uma pasta com fotos (`JPG`, `PNG`, `HEIC`) e vídeos (`MOV`, `MP4`), a skill:

1. Faz inventário (hash `sha256` para duplicadas exatas).
2. Roda análise automática de similaridade (pHash) e qualidade (nitidez, brilho, resolução) + extrai frames dos vídeos.
3. Revisa **visualmente** cada grupo e escolhe a melhor foto (olhos abertos, sorriso, enquadramento limpo).
4. Pede **uma única confirmação** curta antes de organizar.
5. Copia os arquivos para pastas organizadas + gera relatório CSV.

### Antes / depois

```text
pasta-de-midia/
  IMG_001.HEIC   IMG_002.HEIC   IMG_003.JPG   VIDEO.MOV   ...
```

vira:

```text
pasta-de-midia/
  _selecionadas/                    # só o que vale manter
  _descartadas/
    duplicadas/                     # idênticas byte-a-byte ou versões com UI
    muito_parecidas/                # quase iguais, com uma melhor mantida
    baixa_qualidade/                # borradas, escuras, recortes inúteis
  relatorio_triagem.csv             # arquivo,decisao,motivo (1 linha por original)
```

Os arquivos originais **permanecem intactos** na pasta. Tudo é feito por cópia.

## Requisitos

- Python 3.10+
- Dependências (instaladas automaticamente pelo agente ou manualmente):

```bash
pip install -r scripts/requirements.txt
```

## Instalação

### Via CLI `skills` (recomendado)

```bash
npx skills add vitorluigiorsini/media-triage
```

Opções úteis:

```bash
npx skills add vitorluigiorsini/media-triage --list        # só listar o que será instalado
npx skills add vitorluigiorsini/media-triage -g            # instalação global (todas as pastas)
npx skills add vitorluigiorsini/media-triage -a opencode   # só para o OpenCode
npx skills add vitorluigiorsini/media-triage -y            # sem perguntas
```

### Manual

```bash
git clone https://github.com/vitorluigiorsini/media-triage.git
# copie skills/media-triage/SKILL.md para a pasta de skills do seu agente, ex:
#   OpenCode global:  ~/.config/opencode/skills/media-triage/
#   OpenCode projeto: .agents/skills/media-triage/
#   Claude Code:      ~/.claude/skills/media-triage/
```

## Uso

### OpenCode

A skill aparece na lista de skills disponíveis. Para usar, peça ao agente:

> Use a skill media-triage na pasta /caminho/das/fotos

### Claude Code / Gemini CLI / outros

Os agentes detectam a skill automaticamente. Se não ativar sozinha, mencione `media-triage` no prompt.

### Fluxo semi-automático (atrito mínimo)

Você só precisa responder **uma vez** à lista de grupos, com uma linha por grupo:

```text
manter IMG_2741.HEIC | descartar IMG_2740.HEIC (criança de cara fechada)
```

Três formas de responder, da mais rápida à mais fina:

- **a.** `ok` → executa tudo como proposto.
- **b.** `troca A por B no grupo N` → inverte a escolha antes de copiar (ex: "no trio das medalhas, mantém HUFC em vez de QZEH").
- **c.** Correção depois de pronto → `move IMG_X para _selecionadas` (ou o inverso). Como são cópias e os originais estão intactos, a correção é trivial e o CSV é atualizado.

Variações com valor distinto são preservadas (ex: foto do trio + foto do grupo de 6, produtos diferentes na prateleira).

## Como funciona por dentro

| Etapa | Técnica |
|---|---|
| Duplicadas exatas | `sha256` do arquivo |
| Muito parecidas | distância de `pHash` ≤ 12 |
| Nitidez | variância do Laplaciano (OpenCV) — maior = mais nítida |
| Exposição | brilho médio do histograma |
| HEIC | leitura via `pillow-heif` |
| Vídeos | 3 frames (início/meio/fim aprox.) via `imageio-ffmpeg` (traz o binário do ffmpeg, sem instalar nada no sistema) |
| Decisão final | sempre visual, pelo agente — métricas são só pistas |

## Limites conhecidos

- Pastas com 500+ arquivos são processadas em lotes, com resumo por grupo.
- Arquivo corrompido ou HEIC sem suporte é registrado como `img-erro` no CSV e **mantido** por segurança.
- Sem `ffmpeg`, vídeos entram como `sem-preview` e também são mantidos.

## Estrutura do repositório

```text
media-triage/
  skills/media-triage/SKILL.md   # a skill (padrão aberto, name = nome da pasta)
  scripts/triagem.py             # análise: métricas + grupos + frames (não move nada)
  scripts/requirements.txt       # Pillow, pillow-heif, ImageHash, opencv-python, imageio-ffmpeg
```

## Contribuição

Issues e PRs são bem-vindos. Para testar localmente a descoberta da skill:

```bash
npx skills add ./media-triage --list
```

## Licença

MIT — ver [LICENSE](LICENSE).
