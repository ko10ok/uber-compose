from pathlib import Path

import vedro.plugins.temp_keeper as temp_keeper


def mounted_template(content: str, name: str = 'config.yaml') -> str:
    tmp_dir = temp_keeper.create_tmp_dir(prefix='uc-mounted-file-')
    template_path = tmp_dir / name
    template_path.write_text(content)

    return str(template_path.relative_to(Path.cwd()))
