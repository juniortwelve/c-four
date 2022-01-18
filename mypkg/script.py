from mypkg import operate_git
import os
from mypkg.db_settings import Base, engine, session
from mypkg.split_chunks import split_chunks_by_file
from mypkg.models.context import Context
from mypkg.models.add_chunk import AddChunk
from mypkg.models.remove_chunk import RemoveChunk
from mypkg.models.chunk_set import ChunkSet
from mypkg.prompts.main_prompt import generate_main_screen
from prompt_toolkit.shortcuts import yes_no_dialog
from mypkg.operate_json import make_file_unit_json, convert_json_to_data
import json

def main():
    path = os.getcwd()
    repo = operate_git.get_repo(path)
    diffs = operate_git.get_diffs(repo)
    Base.metadata.create_all(engine)
    
    file_unit_json = make_file_unit_json(diffs)
    with open('./json/sample.json', 'w') as f:
        json.dump(file_unit_json, f, ensure_ascii=False, indent=2)
    
    # return None
    
    # for diff in diffs:
    #     context = Context(diff.a_path)
    #     session.add(context)
    #     session.commit()
    #     context.convert_diff_to_chunk(diff.diff.decode())

    convert_json_to_data(file_unit_json)
    while True:
        all_chunks = []
        all_add_chunks = AddChunk.query.all()
        all_remove_chunks = RemoveChunk.query.all()
        all_chunks.extend(all_add_chunks)
        all_chunks.extend(all_remove_chunks)
        
        # split_chunks_by_file(all_chunks)
        chunk_sets = ChunkSet.query.all()
        
        cur_chunk_set_idx = 0
        chunk_sets_size = len(chunk_sets)
        
        #Start and run application
        while cur_chunk_set_idx < chunk_sets_size:
            cur_chunks = []
            cur_chunk_set = chunk_sets[cur_chunk_set_idx]
            cur_chunks.extend(cur_chunk_set.add_chunks)
            cur_chunks.extend(cur_chunk_set.remove_chunks)
            path_sets = {chunk.context.path for chunk in cur_chunks}
            
            # related_chunks = [chunk for chunk in all_chunks if chunk.context.path in path_sets and chunk.chunk_set_id != cur_chunk_set.id]
            related_chunks = []
            pending_chunks = [chunk for chunk in all_chunks if chunk.chunk_set_id is None]
            related_chunks.extend(pending_chunks)
            related_chunks = list(set(related_chunks))
    
            application = generate_main_screen(chunk_sets, cur_chunk_set_idx, related_chunks)
            cur_chunk_set_idx = application.run()
            
        # stage and commit current chunk sets
        for chunk_set in chunk_sets:
            chunk_set.commit_self_chunks(repo)
        
        for chunk_set in chunk_sets:
            for add_chunk in chunk_set.add_chunks:
                AddChunk.query.filter(AddChunk.id == add_chunk.id).delete()
            session.commit()
            for remove_chunk in chunk_set.remove_chunks:
                RemoveChunk.query.filter(RemoveChunk.id == remove_chunk.id).delete()
            session.commit()
            ChunkSet.query.filter(ChunkSet.id == chunk_set.id).delete()
            session.commit()
        
        other_chunks = []
        other_chunks.extend(AddChunk.query.all())
        other_chunks.extend(RemoveChunk.query.all())
    
        if other_chunks:
            result = yes_no_dialog(
                title="Confirm staging of pending chunks",
                text="There is still {} pending chunks.\nDo you want to stage these chunks?".format(len(other_chunks))
            ).run()
            
            if not result:
                break
        else:
            break
        
if __name__ == '__main__':
    main()
