from mypkg.db_settings import session
from prompt_toolkit.application import Application
from prompt_toolkit.layout import HSplit, VSplit, Window, FormattedTextControl, BufferControl, DummyControl, ScrollablePane
from prompt_toolkit.widgets import Box, Frame, Label
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.dimension import D
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from functools import partial
from mypkg.models.add_chunk import AddChunk
from mypkg.models.remove_chunk import RemoveChunk
from mypkg.models.code_info import CodeInfo
from enum import Enum, auto
from prompt_toolkit.formatted_text import FormattedText

class ChunkState(Enum):
    KEEP = auto()
    NEXT = auto()
    PREV = auto()
    PENDING = auto()
    ASSIGN = auto()

CHECKBOXWIDTH = 7

def chunk_selected(text_area, content):
    text_area.text = content

# chunk contents generators
def generate_buffer_key_bindings(text_area, patch, check_box, chunk_state_list, index):
    kb = KeyBindings()
    
    @kb.add("c-m")
    def _(event):
        text_area.text = patch
    
    @kb.add("a")
    def _(event):
        check_box.text = " [*]"
        chunk_state_list[index] = ChunkState.KEEP
    
    @kb.add("d")
    def _(event):
        check_box.text = " [x]"
        chunk_state_list[index] = ChunkState.PENDING
    
    @kb.add("p")
    def _(event):
        check_box.text = " [p]"
        chunk_state_list[index] = ChunkState.PREV
    
    @kb.add("n")
    def _(event):
        check_box.text = " [n]"
        chunk_state_list[index] = ChunkState.NEXT
    
    return kb

def generate_buffer_window(buffer_text, text_area, patch, style, check_box, chunk_state_list, index):
    window = Window(
        BufferControl(
            Buffer(
                document=Document(buffer_text),
                read_only=True
            ),
            focusable=True,
            key_bindings=generate_buffer_key_bindings(text_area, patch, check_box, chunk_state_list, index),
        ),
        height=2,
        style=style,
        width=D(weight=2),
    )
    
    return window

def generate_chunk_buffers(add_chunks, remove_chunks, text_area, check_boxes, chunk_state_list):
    buffers = []
    index = 0
    for add_chunk in add_chunks:
        buffer_text = '{} \n({}, {})'.format(add_chunk.context.path, add_chunk.start_id, add_chunk.end_id)
        buffers.append(generate_buffer_window(buffer_text, text_area, generate_add_patch_with_style(add_chunk), "class:add-chunk", check_boxes[index], chunk_state_list, index))
        index += 1
        
    for remove_chunk in remove_chunks:
        buffer_text = '{} \n({}, {})'.format(remove_chunk.context.path, remove_chunk.start_id, remove_chunk.end_id)
        buffers.append(generate_buffer_window(buffer_text, text_area, generate_remove_patch_with_style(remove_chunk), "class:remove-chunk", check_boxes[index], chunk_state_list, index))
        index += 1
    
    return buffers

def generate_chunks_with_check_box(check_boxes, all_chunks):
    check_box_contents = [Box(body=check_box, style="class:check-box", width=CHECKBOXWIDTH) for check_box in check_boxes]
    return [VSplit([check_box_contents[i], all_chunks[i]]) for i in range(len(all_chunks))]

def generate_main_chunk_components(add_chunks, remove_chunks):
    diff_text = FormattedTextControl(focusable=True)
    diff_area = Window(diff_text)
    
    check_boxes = [Label(text=" [*]") for i in range(len(add_chunks) + len(remove_chunks))]
    state_list = [ChunkState.KEEP for i in range(len(add_chunks) + len(remove_chunks))]
    all_chunks = generate_chunk_buffers(add_chunks, remove_chunks, diff_text, check_boxes, state_list)
    chunk_with_check_boxes = generate_chunks_with_check_box(check_boxes, all_chunks)
    
    return diff_area, all_chunks, state_list, chunk_with_check_boxes

def generate_chunk_with_diff_screen(chunk_with_check_boxes, diff_area):
    check_box_label = generate_label("State", "class:check-box-label", CHECKBOXWIDTH)
    chunk_set_label = generate_label("Chunk Sets", "class:chunk-set-label", D(weight=1))
    
    screen = VSplit(
        [
            HSplit(
                [
                    VSplit([check_box_label, chunk_set_label]),
                    ScrollablePane(
                        HSplit(
                            chunk_with_check_boxes,
                            width=D(max=30, weight=1),
                            style="class:left-pane"
                        )
                    )
                ]
            ),
            HSplit(
                [
                    Label(text="Diff", style="class:diff"),
                    Box(
                        body=Frame(ScrollablePane(diff_area)),
                        padding=0,
                        style='class:right-pane',
                    ),
                ],
                width=D(weight=3),
            ),
        ],
        height=D(),
    )
    
    return screen

# general content generators
def generate_label(text, style, width):
    window = Window(
        FormattedTextControl(text=text),
        height=1,
        width=width,
        style=style,
    )
    return window

def generate_add_patch_with_style(chunk):
    start_id, end_id = chunk.start_id - 3, chunk.start_id + 3
    a_start_id = b_start_id = start_id
    a_line_num = b_line_num = 0
    patch = []
    
    context_codes = CodeInfo.query.filter(CodeInfo.context_id == chunk.context_id, start_id <= CodeInfo.line_id, CodeInfo.line_id <= end_id)
    other_add_chunks = AddChunk.query.filter(start_id <= AddChunk.start_id, AddChunk.start_id <= end_id, AddChunk.id != chunk.id, AddChunk.context_id == chunk.context_id)
    other_remove_chunks = RemoveChunk.query.filter(start_id <= RemoveChunk.start_id, RemoveChunk.start_id <= end_id, RemoveChunk.id != chunk.id, RemoveChunk.context_id == chunk.context_id)
    other_add_chunk_dict = {c.start_id: c.add_chunk_codes for c in other_add_chunks}
    other_remove_chunk_line_ids = set()
    for other_remove_chunk in other_remove_chunks:
        for line_id in range(other_remove_chunk.start_id, other_remove_chunk.end_id + 1):
            other_remove_chunk_line_ids.add(line_id)
    
    for context_code in context_codes:
        line_id = context_code.line_id

        if line_id == chunk.start_id:
            added_count = 0
            for code in chunk.add_chunk_codes:
                patch.append(('class:target-add-line', str(line_id + added_count) + '|+' + code.code + '\n'))
                b_line_num += 1
                added_count += 1

        if line_id in other_add_chunk_dict.keys():
            add_chunk_codes = other_add_chunk_dict[line_id]
            for add_chunk_code in add_chunk_codes:
                patch.append(('class:other-add-line', str(line_id) + '|+' + add_chunk_code.code + '\n'))
                b_line_num += 1
        
        if line_id in other_remove_chunk_line_ids:
            patch.append(('class:other-remove-line', str(line_id) + '|-' + context_code.code + '\n'))
            a_line_num += 1
        else:
            patch.append(('class:default-line', str(line_id) + '| ' + context_code.code + '\n'))
            a_line_num += 1
            b_line_num += 1
    
    patch.insert(0, ('class:patch-label', '@@ -{0},{1} +{2},{3} @@ {4}\n'.format(a_start_id, a_line_num, b_start_id, b_line_num, chunk.context.path)))
    return FormattedText(patch)

def generate_remove_patch_with_style(chunk):
    start_id, end_id = chunk.start_id, chunk.end_id
    removed_count = end_id - start_id + 1
    a_start_id = b_start_id = start_id
    a_line_num, b_line_num = removed_count, 0
    patch = []
    cur_line_num = start_id
    
    for code_info in chunk.context.code_infos:
        if code_info.line_id == start_id - 1:
            cur_line_num = start_id - 1
            patch.append(('class:default-line', str(cur_line_num) + '| ' + code_info.code + '\n'))
            cur_line_num += 1
            a_start_id = b_start_id = code_info.line_id
            a_line_num += 1
            b_line_num += 1
        elif start_id <= code_info.line_id <= end_id:
            patch.append(('class:remove-line', str(cur_line_num) + '|-' + code_info.code + '\n'))
            cur_line_num += 1
        elif code_info.line_id == end_id + 1:
            patch.append(('class:default-line', str(cur_line_num) + '| ' + code_info.code + '\n'))
            cur_line_num += 1
            a_line_num += 1
            b_line_num += 1
    
    patch.insert(0, ('class:patch-label', '@@ -{0},{1} +{2},{3} @@ {4}\n'.format(a_start_id, a_line_num, b_start_id, b_line_num, chunk.context.path)))
    return FormattedText(patch)

# candidate contents generators
def generate_candidate_key_bindings(text_area, patch, check_box, candidate_state_list, index):
    kb = KeyBindings()
    
    @kb.add("c-m")
    def _(event):
        text_area.text = patch
    
    @kb.add("a")
    def _(event):
        check_box.text = " [*]"
        candidate_state_list[index] = ChunkState.ASSIGN
    
    @kb.add("d")
    def _(event):
        check_box.text = " [ ]"
        candidate_state_list[index] = ChunkState.KEEP
    
    return kb

def generate_candidate_window(buffer_text, text_area, patch, style, check_box, candidate_state_list, index):
    window = Window(
        BufferControl(
            Buffer(
                document=Document(buffer_text),
                read_only=True
            ),
            focusable=True,
            key_bindings=generate_candidate_key_bindings(text_area, patch, check_box, candidate_state_list, index),
        ),
        height=3,
        style=style,
        width=D(weight=2)
    )
    
    return window

def generate_candidate_buffers(candidates, text_area, check_boxes, candidate_state_list):
    buffers = []
    index = 0
    for candidate in candidates:
        buffer_text = '{} \n({}, {})\n'.format(candidate.context.path, candidate.start_id, candidate.end_id)
        if candidate.chunk_set_id is not None:
            buffer_text += 'Page: {}'.format(candidate.chunk_set_id)
        else:
            buffer_text += 'Pending'
        
        if isinstance(candidate, AddChunk):
            buffers.append(generate_candidate_window(buffer_text, text_area, generate_add_patch_with_style(candidate), "class:add-chunk", check_boxes[index], candidate_state_list, index))
        else:
            buffers.append(generate_candidate_window(buffer_text, text_area, generate_remove_patch_with_style(candidate), "class:remove-chunk", check_boxes[index], candidate_state_list, index))
        index += 1
    
    return buffers

def generate_other_chunk_components(chunks):
    diff_text = FormattedTextControl(focusable=True)
    diff_area = Window(diff_text)
    
    check_boxes = [Label(text=" [ ]") for i in range(len(chunks))]
    state_list = [ChunkState.KEEP for i in range(len(chunks))]
    all_chunks = generate_candidate_buffers(chunks, diff_text, check_boxes, state_list)
    chunk_with_check_boxes = generate_chunks_with_check_box(check_boxes, all_chunks)
    
    return diff_area, all_chunks, state_list, chunk_with_check_boxes

#other components
def generate_screen_title_label(text, style):
    screen = VSplit(
        [
            Window(DummyControl(), style='class:label-back'),
            Window(DummyControl(), style='class:label-back'),
            Label(text=text, style=style),
            Window(DummyControl(), style='class:label-back'),
            Window(DummyControl(), style='class:label-back'),
        ]
    )
    
    return screen

def generate_move_button(label, focusable, kb, style):
    button = Window(
        BufferControl(
            Buffer(
                document=Document(label),
                read_only=True,
            ),
            focusable=focusable,
            key_bindings=kb
        ),
        height=1,
        style=style,
    )
    
    return button
