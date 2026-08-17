with open(r'D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_viewer.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_json_swallow = """        except Exception as e:
            json_files.append((p.name, f"Error: {e}"))"""
new_json_swallow = """        except Exception as e:
            raise ValueError(f"CRITICAL: Corrupted QCSchema artifact detected at {p}: {e}. Log-and-ignore patterns are forbidden. Fix the upstream generator.") from e"""
content = content.replace(old_json_swallow, new_json_swallow)

old_hdf5_swallow = """                except Exception as e:
                    hdf5_files.append((p.name, f"Error reading: {e}"))"""
new_hdf5_swallow = """                except Exception as e:
                    raise ValueError(f"CRITICAL: Corrupted HDF5 artifact detected at {p}: {e}. Log-and-ignore patterns are forbidden. Fix the upstream generator.") from e"""
content = content.replace(old_hdf5_swallow, new_hdf5_swallow)

with open(r'D:\__CoChem\GitHub-Repo\CoChem-BASE\cochem_viewer.py', 'w', encoding='utf-8') as f:
    f.write(content)
