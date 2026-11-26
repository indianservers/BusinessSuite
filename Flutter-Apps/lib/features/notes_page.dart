import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api_client.dart';

const _notesPath = '/project-management/notes';
const _richPrefix = '<!--suite-richtext:v1-->';

class NotesPage extends StatefulWidget {
  const NotesPage({super.key, required this.api});
  final ApiClient api;

  @override
  State<NotesPage> createState() => _NotesPageState();
}

class _NotesPageState extends State<NotesPage> {
  List<Map<String, dynamic>> _notes = [];
  String _query = '';
  String _view = 'all';
  String? _error;
  bool _loading = true;
  int _request = 0;
  Timer? _debounce;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    final request = ++_request;
    final query = _query.trim();
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result =
          await widget.api.request(
                'GET',
                _notesPath,
                query: {'view': _view, if (query.isNotEmpty) 'q': query},
              )
              as List;
      if (!mounted || request != _request) return;
      setState(() {
        _notes = result.cast<Map<String, dynamic>>();
        _loading = false;
      });
    } catch (error) {
      if (!mounted || request != _request) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  void _open([Map<String, dynamic>? summary]) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => _NoteEditor(api: widget.api, summary: summary),
      ),
    );
    if (mounted) await _load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Notes'),
      actions: [
        PopupMenuButton<String>(
          tooltip: 'Filter notes',
          initialValue: _view,
          onSelected: (view) {
            _view = view;
            _load();
          },
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'all', child: Text('My notes')),
            PopupMenuItem(value: 'shared', child: Text('Shared with me')),
            PopupMenuItem(value: 'archive', child: Text('Archived')),
            PopupMenuItem(value: 'trash', child: Text('Trash')),
          ],
        ),
        IconButton(
          tooltip: 'Refresh notes',
          onPressed: _load,
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    floatingActionButton: FloatingActionButton.extended(
      onPressed: () => _open(),
      icon: const Icon(Icons.add),
      label: const Text('New note'),
    ),
    body: Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: TextField(
            maxLength: 200,
            decoration: const InputDecoration(
              labelText: 'Search notes',
              prefixIcon: Icon(Icons.search),
              counterText: '',
            ),
            onChanged: (value) {
              _query = value;
              _request++;
              _debounce?.cancel();
              _debounce = Timer(const Duration(milliseconds: 250), _load);
            },
          ),
        ),
        if (_loading) const LinearProgressIndicator(),
        if (_error != null)
          Padding(padding: const EdgeInsets.all(16), child: Text(_error!)),
        if (!_loading && _error == null && _notes.isEmpty)
          const Text('No notes found'),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _load,
            child: ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.only(bottom: 88),
              itemCount: _notes.length,
              itemBuilder: (context, index) {
                final note = _notes[index];
                return ListTile(
                  title: Text(
                    note['title'] as String? ?? 'Untitled note',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  subtitle: Text(
                    note['preview'] as String? ?? '',
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  onTap: () => _open(note),
                );
              },
            ),
          ),
        ),
      ],
    ),
  );
}

class _NoteEditor extends StatefulWidget {
  const _NoteEditor({required this.api, this.summary});
  final ApiClient api;
  final Map<String, dynamic>? summary;

  @override
  State<_NoteEditor> createState() => _NoteEditorState();
}

class _NoteEditorState extends State<_NoteEditor> {
  final _title = TextEditingController();
  final _body = TextEditingController();
  Map<String, dynamic>? _note;
  String? _error;
  bool _loading = false;
  bool _saving = false;
  bool _dirty = false;

  bool get _rich =>
      (_note?['content'] as String? ?? '').startsWith(_richPrefix);
  bool get _editable =>
      widget.summary == null && _note == null ||
      _note?['can_edit'] == true && _note?['deleted_at'] == null;

  @override
  void initState() {
    super.initState();
    if (widget.summary != null) _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final note =
          await widget.api.request(
                'GET',
                '$_notesPath/${widget.summary!['id']}',
              )
              as Map<String, dynamic>;
      if (!mounted) return;
      setState(() => _note = note);
      _title.text = note['title'] as String? ?? '';
      _body.text = _rich
          ? (widget.summary?['preview'] as String? ?? '')
          : (note['content'] as String? ?? '');
    } catch (error) {
      if (mounted) setState(() => _error = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _save() async {
    if (_saving || !_dirty || !_editable) return;
    final note = _note;
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.request(
        note == null ? 'POST' : 'PUT',
        note == null ? _notesPath : '$_notesPath/${note['id']}',
        data: {
          'title': _title.text,
          'content': _rich ? note!['content'] : _body.text,
          if (note != null)
            for (final key in [
              'version',
              'project_id',
              'task_id',
              'folder_id',
              'tags',
              'pinned',
              'favorite',
              'archived',
            ])
              key: note[key],
        },
      );
      if (!mounted) return;
      setState(() {
        _dirty = false;
        _saving = false;
      });
      Navigator.of(context).pop();
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = error is ApiFailure && error.status == 409
            ? 'This note changed elsewhere. Your edits are still here. Copy them before reopening the latest version.'
            : error.toString();
      });
    }
  }

  void _changed(String _) {
    if (!_dirty) setState(() => _dirty = true);
  }

  @override
  void dispose() {
    _title.dispose();
    _body.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !_dirty && !_saving,
    onPopInvokedWithResult: (didPop, _) async {
      if (didPop || _saving || !_dirty) return;
      final discard = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Discard unsaved edits?'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Keep editing'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Discard'),
            ),
          ],
        ),
      );
      if (discard == true && context.mounted) Navigator.of(context).pop();
    },
    child: Scaffold(
      appBar: AppBar(
        title: Text(widget.summary == null ? 'New note' : 'Note'),
        actions: [
          TextButton(
            onPressed: _editable && _dirty && !_saving ? _save : null,
            child: Text(_saving ? 'Saving…' : 'Save'),
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(20),
              children: [
                if (_error != null) Text(_error!),
                if (widget.summary != null && _note == null)
                  TextButton(onPressed: _load, child: const Text('Retry'))
                else ...[
                  TextField(
                    controller: _title,
                    readOnly: !_editable || _saving,
                    maxLength: 180,
                    onChanged: _changed,
                    decoration: const InputDecoration(labelText: 'Title'),
                  ),
                  if (_rich)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: Text(
                        'Formatted note preview. Edit the full document on the web.',
                      ),
                    ),
                  TextField(
                    controller: _body,
                    readOnly: !_editable || _saving || _rich,
                    minLines: 10,
                    maxLines: null,
                    onChanged: _changed,
                    decoration: InputDecoration(
                      labelText: _rich ? 'Preview' : 'Note',
                    ),
                  ),
                ],
              ],
            ),
    ),
  );
}
