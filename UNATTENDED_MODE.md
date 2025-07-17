# Unattended Mode for Slivka Bio Installer

The installation script now supports an unattended mode that eliminates all interactive prompts, making it suitable for automated deployments and CI/CD pipelines.

## New Command Line Options

### `--unattended` / `-y`
Enables unattended mode where all interactive prompts are bypassed.

### `--prefer-installer [conda|docker]`
Specifies the preferred installer when both conda and docker installers are available for a service. 
- If not specified, conda is preferred over docker by default
- Only applies when `--unattended` is used

### `--overwrite`
Automatically overwrite existing files and environments without prompting.
- Applies to data directories and conda environments
- When not used in unattended mode, existing files/environments are preserved

### `--on-error [retry|skip|abort]`
Specifies the action to take when installation errors occur in unattended mode:
- `skip` (default): Skip the failed service and continue with the next one
- `abort`: Stop the entire installation process
- `retry`: Keep retrying the same service indefinitely (use with caution)

## Usage Examples

### Basic unattended installation
```bash
python install.py --unattended /path/to/target/directory
```

### Unattended installation with preferences
```bash
python install.py --unattended --prefer-installer conda --overwrite --on-error skip /path/to/target/directory
```

### Install specific services in unattended mode
```bash
python install.py --unattended --service clustalo --service muscle /path/to/target/directory
```
