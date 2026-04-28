import os, sys, shutil
from pathlib import Path
sys.path.insert(0, '.')

from leaper_config import load_leaper_config, config_to_hermes_env, write_hermes_config

cfg = load_leaper_config('leaper.yaml')
env_vars = config_to_hermes_env(cfg)
for k, v in env_vars.items():
    os.environ[k] = v

# Copy CEO Coach template files
template_dir = Path('templates/ceo-coach')
for f in template_dir.glob('*.md'):
    if not Path(f.name).exists():
        shutil.copy(f, '.')
        print(f'Copied {f.name}')

write_hermes_config(cfg)
print('Config written')

home = os.environ.get('HERMES_HOME', 'not set')
token = os.environ.get('TELEGRAM_BOT_TOKEN', 'not set')[:20]
base = os.environ.get('OPENAI_BASE_URL', 'not set')
model = os.environ.get('HERMES_MODEL', 'not set')
print(f'HERMES_HOME={home}')
print(f'TOKEN={token}...')
print(f'BASE_URL={base}')
print(f'MODEL={model}')
