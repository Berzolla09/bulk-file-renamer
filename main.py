from file_renamer import FileRenamer

from file_renamer import FileRenamer


def main():
    root_directory = '/path/to/root/directory'

    action = 'rename'  # 'rename', 'undo', or 'redo'
    log_file_path = '/path/to/rename-log.json'

    renamer = FileRenamer(
        root_directory=root_directory,
        order='date-dsc',
        number_format='decimal',
        separator='-',
        case='lower',
        log=True
    )

    match action:
        case 'rename':
            operations, log_file = renamer.rename()
            print(f'Renamed {len(operations)} files.')

            if log_file:
                print(f'Log saved to: {log_file.as_posix()}')
        case 'undo':
            renamer.undo(log_file_path)
        case 'redo':
            renamer.redo(log_file_path)
        case _:
            raise ValueError(f'Unknown action: {action}')

if __name__ == '__main__':
    main()
