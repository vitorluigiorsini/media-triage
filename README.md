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
  _selecionadas/
    cenas/                          # fotos e vídeos com pessoa/ambiente (padrão)
    objetos/                        # coisa isolada: close-up, peça, produto (só se houver)
    prints/                         # screenshots, convites, artes digitais (só se houver)
  _descartadas/
    duplicadas/                     # idênticas byte-a-byte ou versões com UI
    similares/                      # quase iguais, com uma melhor mantida
    baixa_qualidade/                # borradas, escuras, recortes inúteis
  relatorio_triagem.csv             # arquivo,decisao,motivo,categoria (1 linha por original)
```

Subpastas de `_selecionadas/` e `_descartadas/` só são criadas quando têm conteúdo — nunca pastas vazias. Todo o resto (cenas, pessoas e vídeos, que são cenas em movimento) fica em `cenas/`.

Os arquivos originais **permanecem intactos** na pasta. Tudo é feito por cópia.

## Requisitos

- Python 3.10+
- Dependências (instaladas automaticamente pelo agente ou manualmente):

```bash
pip install -r scripts/requirements.txt
```

### Notas por sistema operacional

A skill funciona em **Linux, macOS e Windows** sem mudança de código (o script usa só `os.path`, e o `imageio-ffmpeg` baixa o binário do ffmpeg correto para cada OS). Pontos de atenção:

- **Windows:** instale o Python 3.10+ em python.org marcando **"Add python.exe to PATH"** (erro mais comum); rode os comandos no Git Bash ou PowerShell; o `npx skills add ...` funciona no CMD/PowerShell com Node.js instalado.
- **macOS:** garanta `python3` e `pip` (via Xcode Command Line Tools, python.org ou Homebrew); há wheels prontos para Intel e Apple Silicon em todas as dependências.
- **Geral:** passe a pasta sempre entre aspas (caminhos com espaços/acentos funcionam); extensões são comparadas em minúsculas, então filesystems case-insensitive não quebram nada.

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

### Exemplo de uso

Suponha a skill instalada e uma pasta bagunçada em `"/home/vitororsini/Downloads/viagem_julho"`:

**1. Você chama (o caminho da pasta é o único dado obrigatório):**

> Use a skill media-triage na pasta "/home/vitororsini/Downloads/viagem_julho"

Não precisa de slash command (`/media-triage` não existe nem é necessário): o agente identifica a skill pela descrição e carrega as instruções sozinho. Mencionar `media-triage` no pedido ajuda, mas até *"separa as fotos boas da pasta X"* funciona.

**2. O agente trabalha sozinho:** inventário (`sha256`), análise automática (`scripts/triagem.py` → `_tmp_metricas.csv` + frames dos vídeos) e revisão visual de cada grupo suspeito.

**3. Você confirma uma vez:**

```text
Grupo 1 (pôr do sol, 4 fotos): manter IMG_1024.HEIC | descartar as outras 3 (foco pior)
Grupo 2 (selfie praia, 2 fotos): manter IMG_1031.JPG | descartar IMG_1030.JPG (olhos fechados)
Grupo 3 (nota fiscal, 1 foto): manter em prints/ (só ela na categoria)
Demais 40 arquivos: únicos, mantidos em cenas/
```

Responda `ok` — ou `troca A por B no grupo 2`, se discordar de algo.

**4. O agente organiza:** copia (nunca apaga originais) para `_selecionadas/cenas|objetos|prints/` e `_descartadas/...`, gera `relatorio_triagem.csv`, limpa os `_tmp_*` e resume o resultado.

**5. Correção tardia:** os originais seguem intactos, então basta pedir `move IMG_1030 para _selecionadas/cenas` — o agente move e atualiza o CSV, sem reprocessar nada.

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
- Em tiers gratuitos com limite de imagens por request, a skill pagina a revisão visual automaticamente (máx. ~10 imagens por mensagem).
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
