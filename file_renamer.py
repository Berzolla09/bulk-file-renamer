import json
import re
import uuid
from datetime import datetime
from pathlib import Path

class FileRenamer():
    def __init__(self, root_directory:str|Path, order:str='date-dsc', number_format:str='decimal', separator:str='-', case:str='lower', log:bool=True) -> None:
        """
        Initialize the file renamer.

        Args:
            root_directory: Root directory containing subdirectories to process.
            order: Sorting method used before renaming files.
            number_format: Numbering format to use, either 'decimal' or 'hex'.
            separator: String used to separate words and sequence numbers.
            case: Case format used for generated filenames.
            log: Whether to create a rename log.
        """
        
        self.root_directory = Path(root_directory).absolute()
        self.order = order
        self.number_format = number_format
        self.separator = separator
        self.case = case
        self.log = log
        
    def format_prefix(self, name:str) -> str:
        """
        Format a directory name for use as a filename prefix.

        Args:
            name: Directory name to format.

        Returns:
            The formatted filename prefix.

        Raises:
            ValueError: If the configured case format is invalid.
        """
    
        words = [word for word in re.split(r'[\s_-]+', name.strip()) if word]

        match self.case.lower():
            case 'keep' | 'none':
                return self.separator.join(words)
            case 'lower':
                return self.separator.join(word.lower() for word in words)
            case 'upper':
                return self.separator.join(word.upper() for word in words)
            case 'title':
                return self.separator.join(word.capitalize() for word in words)
            case 'camel' | 'camelcase':
                if not words:
                    return ''
                return (words[0].lower() + ''.join(word.capitalize() for word in words[1:]))
            case 'pascal' | 'uppercamel' | 'uppercamelcase':
                return ''.join(word.capitalize() for word in words)
            case _:
                raise ValueError(f'Unknown case format: {self.case}')

    def sort_files(self, files:list[Path]) -> list[Path]:
        """
        Sort files according to the configured sort order.

        Args:
            files: Files to sort.

        Returns:
            The sorted list of files.

        Raises:
            ValueError: If the configured sort order is invalid.
        """

        match self.order:
            case 'date-asc':
                files.sort(key=lambda file: (file.stat().st_mtime, file.name.lower()))
            case 'date-dsc':
                files.sort(key=lambda file: (-file.stat().st_mtime, file.name.lower()))
            case 'name-asc':
                files.sort(key=lambda file: file.name.lower())
            case 'name-dsc':
                files.sort(key=lambda file: file.name.lower(), reverse=True)
            case 'size-asc':
                files.sort(key=lambda file: (file.stat().st_size, file.name.lower()))
            case 'size-dsc':
                files.sort(key=lambda file: (-file.stat().st_size, file.name.lower()))
            case 'extension':
                files.sort(key=lambda file: (file.suffix.lower(), file.name.lower()))
            case _:
                raise ValueError(f'Unknown order: {self.order}')
        return files

    def format_number(self, number:int, file_count:int) -> str:
        """
        Format a sequence number using the configured number format.

        Padding is calculated automatically from the total number of files.
        Decimal numbering starts at 1, while hexadecimal numbering starts at 0.

        Args:
            number: Current sequence number.
            file_count: Total number of files being renamed.

        Returns:
            The formatted sequence number.

        Raises:
            ValueError: If the configured number format is invalid.
        """
        
        match self.number_format:
            case 'dec' | 'decimal':
                width = len(str(file_count))
                return f'{number:0{width}d}'
            case 'hex' | 'hexadecimal':
                width = len(f'{max(file_count - 1, 0):x}')
                return f'{number - 1:0{width}x}'
            case _:
                raise ValueError(f'Unknown number format: {self.number_format}')

    def _rename_files(self, directory:str|Path) -> list[dict[str, str]]:
        """
        Rename all files in a directory using the configured options.

        Files are temporarily renamed before receiving their final names to
        prevent filename collisions.

        Args:
            directory: Directory containing the files to rename.

        Returns:
            A list of rename operations containing the original and new paths.
        """
        
        directory = Path(directory)
        prefix = self.format_prefix(directory.name)

        files:list[Path] = [file for file in directory.iterdir() if file.is_file()]
        files = self.sort_files(files)

        original_files: list[Path] = list(files)
        temp_files:list[Path] = []
        operations: list[dict[str, str]] = []

        for file in files:
            temp_path = directory / f'.rename-temp-{uuid.uuid4().hex}{file.suffix}'
            file.rename(temp_path)
            temp_files.append(temp_path)

        for i, file in enumerate(temp_files, start=1):
            number = self.format_number(i, len(files))
            new_path:Path = directory / f'{prefix}{self.separator}{number}{file.suffix}'
            old_path:Path = original_files[i - 1]

            file.rename(new_path)

            operations.append({
                'old_name': old_path.name,
                'new_name': new_path.name,
                'old_path': str(old_path.absolute()),
                'new_path': str(new_path.absolute())
            })

        return operations

    def rename(self, log_file:str|Path|None =None) -> tuple[list[dict[str, str]], Path|None]:
        """
        Rename files in each subdirectory of the root directory.

        Args:
            log_file: Optional path for the rename log.

        Returns:
            A tuple containing the rename operations and saved log path.
        """
        
        operations: list[dict[str, str]] = []

        for subdirectory in self.root_directory.iterdir():
            if subdirectory.is_dir():
                operations.extend(self._rename_files(subdirectory))

        saved_log: Path | None = None

        if self.log and operations:
            saved_log = self.save_log(operations, log_file)

        return operations, saved_log
    
    def save_log(self, operations:list[dict[str, str]], log_file:str|Path|None=None) -> Path:
        """
        Save rename operations to a JSON log file.

        Args:
            operations: Rename operations containing original and new file paths.
            log_file: Optional path for the log file. If omitted, a timestamped
                filename is generated automatically.

        Returns:
            The path to the saved log file.
        """
        
        if log_file is None:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
            log_file = self.root_directory / f'rename-log-{timestamp}.json'
        else:
            log_file = Path(log_file)

        log_data = {
            'created': datetime.now().astimezone().isoformat(),
            'root_directory': str(self.root_directory),
            'operations': operations
        }

        with log_file.open('w', encoding='utf-8') as file:
            json.dump(log_data, file, indent=4)

        return log_file

    def _apply_log(self, log_file:str|Path, action:str) -> None:
        """
        Apply a rename log as an undo or redo operation.

        Args:
            log_file: Path to the JSON rename log.
            action: Action to perform, either 'undo' or 'redo'.

        Raises:
            ValueError: If the action is invalid.
            FileNotFoundError: If a source file is missing.
            FileExistsError: If a target filename is already occupied.
        """
        
        match action:
            case 'undo':
                source_key:str = 'new_path'
                target_key:str = 'old_path'
            case 'redo':
                source_key:str = 'old_path'
                target_key:str = 'new_path'
            case _:
                raise ValueError(f'Unknown action: {action}')

        log_path:Path = Path(log_file)
        log_data:dict = json.loads(log_path.read_text(encoding='utf-8'))
        operations:list[dict[str, str]] = log_data['operations']

        missing:list[str] = [
            operation[source_key]
            for operation in operations
            if not (self.root_directory / operation[source_key]).exists()
        ]

        if missing:
            raise FileNotFoundError(f'Cannot {action} because these files are missing:\n' + '\n'.join(missing))

        source_paths:set[Path] = {
            (self.root_directory / operation[source_key]).absolute()
            for operation in operations
        }

        operation:dict[str, str]

        for operation in operations:
            target_path:Path = (self.root_directory / operation[target_key]).absolute()

            if target_path.exists() and target_path not in source_paths:
                raise FileExistsError(f'Cannot {action} "{target_path}" because a file already exists there.')

        temp_operations:list[tuple[Path, Path]] = []

        for operation in operations:
            source_path:Path = self.root_directory / operation[source_key]
            target_path:Path = self.root_directory / operation[target_key]
            temp_path:Path = source_path.with_name(f'.{action}-temp-{uuid.uuid4().hex}{source_path.suffix}')

            source_path.rename(temp_path)
            temp_operations.append((temp_path, target_path))

        temp_path:Path
        target_path:Path

        for temp_path, target_path in temp_operations:
            temp_path.rename(target_path)

        print(f'{action.capitalize()} complete: {len(operations)} files renamed.')
        
    def undo(self, log_file:str|Path) -> None:
        """
        Restore original filenames using a previously generated rename log.

        Args:
            log_file: Path to the JSON rename log containing the rename operations.

        Raises:
            FileNotFoundError: If a renamed file listed in the log is missing.
            FileExistsError: If an original filename is already occupied by another file.
        """
        
        self._apply_log(log_file, 'undo')

    def redo(self, log_file:str|Path) -> None:
        """
        Reapply renamed filenames using a previously generated rename log.

        Args:
            log_file: Path to the JSON rename log containing the rename operations.

        Raises:
            FileNotFoundError: If an original file listed in the log is missing.
            FileExistsError: If a renamed filename is already occupied by another file.
        """
        
        self._apply_log(log_file, 'redo')

