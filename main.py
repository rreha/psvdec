from psvdec import *

if os.path.isdir("./tmp"):
    shutil.rmtree("./tmp")
if os.path.isdir("./Decrypted"):
    shutil.rmtree("./Decrypted")

clear_screen()
print("psvdec ~ PS Vita Content Decryptor ~ https://github.com/rreha/psvdec\n")
to_process = []
inputs = get_input()

for i in inputs:
    if os.path.isdir(i):
        print(">    Folder detected.")
        to_process.append(i)

    elif os.path.isfile(i):
        if os.path.splitext(i)[1] == ".pkg":
            print(">    PKG detected.")
            print(">    Extracting...")
            extract_pkg(i)
            extracted = "./tmp/" + os.listdir("./tmp/")[0]
            to_process.append(extracted)

        else:
            print_exit("/!\\    Please make sure that the specified file is a .pkg file.")

    else:
        print_exit("/!\\    Couldn't detect input. Maybe it doesn't exist? Please run the program again.")

    to_process = list(set(to_process))
    
for folder in to_process:
    is_dlc = detect_content(folder)
    content_id_list = get_content_id(folder)

    for content_id in content_id_list:
        if is_dlc:
            dlc_id_list = get_dlc_id(folder, content_id)
            for dlc_id in dlc_id_list:
                print(f">    Searching zRIF key for {content_id}/{dlc_id} (might take a while).")
                zrif = get_zrif(content_id, is_dlc, dlc_id=dlc_id)
                decrypt_pfs(folder, content_id, zrif, dlc_id_list=dlc_id_list, dlc_id=dlc_id)
        else:
            print(f">    Searching zRIF key for {content_id} (might take a while).")
            zrif = get_zrif(content_id, is_dlc)
            decrypt_pfs(folder, content_id, zrif)
            decrypt_eboot(zrif)

if os.path.exists("./tmp"):
    shutil.rmtree("./tmp")