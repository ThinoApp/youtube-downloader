# Playlist Downloader

Application desktop Python pour analyser et télécharger une playlist YouTube en une seule opération avec **yt-dlp**.

## Fonctionnalités

- analyse de la playlist avant téléchargement ;
- téléchargement de toute la playlist ;
- téléchargement d'une plage (`10` à `25`) ;
- sélection personnalisée (`1,3,7,10-15`) ;
- sortie vidéo MP4 ou WebM ;
- extraction audio MP3 ou M4A ;
- limite de qualité : meilleure disponible, 1080p, 720p, 480p ou 360p ;
- progression, vitesse et ETA ;
- annulation du téléchargement ;
- reprise des fichiers partiels via yt-dlp ;
- archive locale pour éviter de retélécharger les mêmes vidéos ;
- organisation automatique par nom de playlist et index.

## Prérequis

- Python 3.10 ou supérieur ;
- [FFmpeg](https://ffmpeg.org/) accessible dans le `PATH` pour fusionner vidéo/audio et pour les sorties MP3/M4A.

## Installation

```bash
git clone https://github.com/ThinoApp/youtube-downloader.git
cd youtube-downloader
python -m venv .venv
```

### Windows

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### macOS / Linux

```bash
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Tu peux aussi installer le projet comme paquet local :

```bash
pip install -e .
playlist-downloader
```

## Utilisation

1. Colle l'URL d'une playlist YouTube.
2. Clique sur **Analyser**.
3. Choisis :
   - toute la playlist ;
   - une plage d'index ;
   - une sélection personnalisée comme `1,3,7,10-15`.
4. Choisis le format et la qualité.
5. Sélectionne le dossier de destination.
6. Clique sur **Télécharger**.

Les fichiers sont rangés ainsi :

```text
Téléchargements/
└── Nom de la playlist/
    ├── 001 - Titre de la vidéo [id].mp4
    ├── 002 - Titre de la vidéo [id].mp4
    └── ...
```

Le fichier `.yt-dlp-archive.txt` créé dans le dossier de destination mémorise les vidéos déjà téléchargées.

## Tests

Les tests inclus ne nécessitent pas d'accès réseau :

```bash
python -m unittest discover -s tests -v
```

## Structure

```text
.
├── app.py
├── pyproject.toml
├── requirements.txt
├── tests/
│   └── test_selection.py
└── youtube_downloader/
    ├── app.py
    ├── downloader.py
    ├── models.py
    ├── selection.py
    ├── ui.py
    └── workers.py
```

## Utilisation responsable

Télécharge uniquement les contenus que tu possèdes ou pour lesquels tu disposes de l'autorisation nécessaire. L'utilisateur reste responsable du respect des droits d'auteur, des conditions des plateformes et des lois applicables.
