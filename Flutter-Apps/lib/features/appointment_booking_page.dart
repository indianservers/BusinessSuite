import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';

import '../core/api_client.dart';
import '../core/models.dart';
import 'sales_order_drafts_page.dart';

class AppointmentBookingPage extends StatefulWidget {
  const AppointmentBookingPage({
    super.key,
    required this.api,
    required this.headers,
    this.linkedAppointmentId,
  });

  final ApiClient api;
  final Map<String, String> headers;
  final int? linkedAppointmentId;

  @override
  State<AppointmentBookingPage> createState() => _AppointmentBookingPageState();
}

class _AppointmentBookingPageState extends State<AppointmentBookingPage> {
  static const _optionsPath = '/srm/service-checkout/options';
  late final _revision = widget.api.sessionRevision;
  Json? _customer, _service, _options, _provider, _slot, _pending;
  List<Json> _slots = [];
  final _resources = <int>{};
  late DateTime _day = DateUtils.dateOnly(DateTime.now());
  int? _minutes;
  String? _notice;
  bool _busy = false;
  bool get _active => mounted && widget.api.sessionRevision == _revision;
  Json? get _policy => _options?['policy'] as Json?;
  Json? _schedule;
  String? get _schedulePath => widget.linkedAppointmentId == null
      ? null
      : '/srm/service-checkout/appointments/${widget.linkedAppointmentId}/schedule';

  @override
  void initState() {
    super.initState();
    if (_schedulePath != null) _loadSchedule();
  }

  Future<void> _loadSchedule() => _run(() async {
    final schedule = await _get(_schedulePath!);
    final booking = schedule['booking'] as Json;
    final id = schedule['service_id'];
    final options = await _get(_optionsPath, {'service_id': id});
    if (!_active) return;
    setState(() {
      _schedule = schedule;
      _options = options;
      _service = {'id': id, 'name': (options['service'] as Json?)?['name']};
      _provider = _rows(options, 'specialists')
          .where(
            (provider) =>
                provider['eligibility_id'] == booking['eligibility_id'],
          )
          .firstOrNull;
      _minutes = booking['duration_minutes'] as int?;
      _resources
        ..clear()
        ..addAll((schedule['additional_resource_ids'] as List).cast<int>());
      _clearSlots();
    });
  });

  List<Json> _rows(Json? value, String key) =>
      (value?[key] as List? ?? const []).whereType<Json>().toList();

  Future<Json> _get(String path, [Map<String, dynamic>? query]) async =>
      await widget.api.request(
            'GET',
            path,
            query: query,
            scopeHeaders: widget.headers,
          )
          as Json;

  Future<void> _run(Future<void> Function() action) async {
    if (_busy || !_active) return;
    setState(() {
      _busy = true;
      _notice = null;
    });
    try {
      await action();
    } catch (error) {
      if (_active) setState(() => _notice = '$error');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _clearSlots() {
    _slots = [];
    _slot = null;
  }

  Future<void> _chooseCustomer() async {
    final choice = await showDialog<Json>(
      context: context,
      builder: (_) => SalesRecordPicker(
        api: widget.api,
        offline: false,
        scopeHeaders: widget.headers,
      ),
    );
    if (_active && choice != null) setState(() => _customer = choice);
  }

  Future<void> _chooseService() async {
    final choice = await showDialog<Json>(
      context: context,
      builder: (_) => _ServicePicker(
        load: (search, page) {
          return _get('/catalog/items', {
            'source': 'srm',
            'kind': 'service',
            'status': 'Active',
            'search': search,
            'page': page,
            'per_page': 30,
          });
        },
      ),
    );
    if (!_active || choice == null) return;
    setState(() {
      _service = choice;
      _options = null;
      _provider = null;
      _minutes = null;
      _resources.clear();
      _clearSlots();
    });
    await _run(() async {
      final options = await _get(_optionsPath, {'service_id': choice['id']});
      if (!_active) return;
      setState(() {
        _options = options;
        _minutes = _policy?['default_duration_minutes'] as int?;
      });
    });
  }

  Future<void> _pickDay() async {
    final day = await showDatePicker(
      context: context,
      initialDate: _day,
      firstDate: DateUtils.dateOnly(DateTime.now()),
      lastDate: DateTime.now().add(const Duration(days: 365)),
    );
    if (_active && day != null) {
      setState(() {
        _day = day;
        _clearSlots();
      });
    }
  }

  String get _dayKey =>
      MaterialLocalizations.of(context).formatMediumDate(_day);

  Future<Json> _availability({String? startsAt}) =>
      _get('$_optionsPath/availability', {
        'service_id': _service!['id'],
        'eligibility_id': _provider!['eligibility_id'],
        'day': _day.toIso8601String().split('T').first,
        'duration_minutes': _minutes,
        if (_resources.isNotEmpty) 'resource_ids': _resources.toList(),
        'starts_at': ?startsAt,
      });

  Future<void> _loadSlots() => _run(() async {
    setState(_clearSlots);
    final result = await _availability();
    if (!_active) return;
    setState(() {
      _slots = _rows(result, 'slots');
      if (_slots.isEmpty) _notice = 'No times available for this selection.';
    });
  });

  Future<void> _confirm() => _run(() async {
    if (_pending == null) {
      final latest = await _get(_optionsPath, {'service_id': _service!['id']});
      if (!_active) return;
      final previousQuote = _options?['service'] as Json?;
      final latestQuote = latest['service'] as Json?;
      final updatedPolicy = latest['policy'] as Json?;
      if (updatedPolicy?['revision'] != _policy?['revision']) {
        setState(() {
          _options = latest;
          _provider = null;
          _minutes = _policy?['default_duration_minutes'] as int?;
          _resources.clear();
          _clearSlots();
          _notice =
              'The booking rules changed. Review the service and choose a time again.';
        });
        return;
      }
      if (latestQuote?['price'] != previousQuote?['price'] ||
          latestQuote?['currency'] != previousQuote?['currency']) {
        setState(() {
          // Keep the selected provider and time while the user reviews the price.
          _options = {..._options!, 'service': latestQuote};
          _notice = 'The estimated price changed. Review it before confirming.';
        });
        return;
      }
      final start = _slot!['starts_at'] as String;
      final fresh = await _availability(startsAt: start);
      if (!_active) return;
      if (fresh['selection_available'] != true) {
        setState(() {
          _clearSlots();
          _notice =
              'This time is no longer available. Check available times again.';
        });
        return;
      }
      final provider = _provider!;
      final title = '${_service!['name']} · ${_customer?['name'] ?? ''}';
      _pending = {
        'request_id': const Uuid().v4(),
        'title': String.fromCharCodes(title.runes.take(220)),
        'customer_id': ?_customer?['id'],
        'service_id': _service!['id'],
        'resource_ids': [provider['provider_resource_id'], ..._resources],
        'starts_at': start,
        'duration_minutes': _minutes,
        'booking': {
          'policy_id': _policy!['id'],
          'expected_policy_revision': _policy!['revision'],
          'eligibility_id': provider['eligibility_id'],
          'expected_eligibility_revision': provider['eligibility_revision'],
          'provider_resource_id': provider['provider_resource_id'],
          'employee_id': provider['employee_id'],
          'additional_resource_ids': _resources.toList(),
          'starts_at': start,
          'duration_minutes': _minutes,
        },
      };
    }
    final grouped = _schedule;
    try {
      final result = await widget.api.request(
        'POST',
        _schedulePath ?? '/srm/industry/appointments',
        data: grouped == null
            ? _pending
            : {
                'expected_appointment_revision':
                    grouped['appointment_revision'],
                'expected_occurrence_revision': grouped['occurrence_revision'],
                'booking': _pending!['booking'],
                'additional_resource_ids': _resources.toList(),
              },
        scopeHeaders: widget.headers,
      );
      if (!mounted || widget.api.sessionRevision != _revision) return;
      final appointment = grouped == null
          ? result
          : (result is Json ? result['appointment'] : null);
      if (appointment is! Json || appointment['id'] is! int) {
        throw ApiFailure('Booking confirmation is unavailable.', 503);
      }
      if (grouped != null && result is Json && result['schedule'] is Json) {
        final confirmed = result['schedule'] as Json;
        final booking = confirmed['booking'] as Json;
        final record = Map<String, dynamic>.of(appointment['data'] as Json)
          ..remove('ends_at');
        Navigator.pop(context, {
          ...appointment,
          'revision': confirmed['appointment_revision'],
          'data': {
            ...record,
            'starts_at': booking['starts_at'],
            'duration_minutes': booking['duration_minutes'],
            'resource_ids': [
              booking['provider_resource_id'],
              ...(confirmed['additional_resource_ids'] as List),
            ],
          },
        });
        return;
      }
      Navigator.pop(context, appointment);
    } on ApiFailure catch (failure) {
      if (_active && const {400, 403, 404, 409, 422}.contains(failure.status)) {
        setState(() {
          _pending = null;
          _clearSlots();
        });
      }
      rethrow;
    }
  });

  @override
  Widget build(BuildContext context) {
    final grouped = _schedulePath != null;
    final edit = !_busy && _pending == null;
    final options = _options;
    final providers = _rows(options, 'specialists');
    final resources = _rows(options, 'resources');
    final quote = options?['service'] as Json?;
    final canCheck = edit && _provider != null && _minutes != null;
    return Scaffold(
      appBar: AppBar(
        title: Text(grouped ? 'Reschedule service' : 'New appointment'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (grouped)
            OutlinedButton(
              onPressed: _busy
                  ? null
                  : () {
                      setState(() {
                        _pending = null;
                        _schedule = null;
                        _provider = null;
                        _clearSlots();
                      });
                      _loadSchedule();
                    },
              child: const Text('Reload current schedule'),
            )
          else ...[
            OutlinedButton(
              onPressed: edit ? _chooseCustomer : null,
              child: Text('${_customer?['name'] ?? 'Choose customer'}'),
            ),
            OutlinedButton(
              onPressed: edit ? _chooseService : null,
              child: Text('${_service?['name'] ?? 'Choose service'}'),
            ),
          ],
          if (grouped && _service != null) Text('${_service!['name']}'),
          if (quote != null)
            Text(
              'Estimated price before tax: ${quote['currency']} ${quote['price']}',
            ),
          if (options != null && providers.isEmpty)
            const Text(
              'No eligible providers are configured for this service.',
            ),
          if (providers.isNotEmpty)
            DropdownButton<Json>(
              isExpanded: true,
              hint: const Text('Choose provider'),
              value: _provider,
              items: [
                for (final person in providers)
                  DropdownMenuItem(
                    value: person,
                    child: Text('${person['employee_name']}'),
                  ),
              ],
              onChanged: edit
                  ? (person) => setState(() {
                      _provider = person;
                      _clearSlots();
                    })
                  : null,
            ),
          if (_provider != null) ...[
            OutlinedButton(
              onPressed: edit ? _pickDay : null,
              child: Text(_dayKey),
            ),
            Text('Provider time zone: ${_provider!['timezone']}'),
            if (_policy?['allow_duration_override'] == true)
              TextFormField(
                key: ValueKey(_service!['id']),
                initialValue: '$_minutes',
                enabled: edit,
                keyboardType: TextInputType.number,
                decoration: InputDecoration(
                  labelText: 'Duration in minutes',
                  helperText:
                      "${_policy!['min_duration_minutes']}–${_policy!['max_duration_minutes']} minutes",
                ),
                onChanged: (value) => setState(() {
                  final parsed = int.tryParse(value);
                  final min = _policy!['min_duration_minutes'] as int;
                  final max = _policy!['max_duration_minutes'] as int;
                  _minutes = parsed != null && parsed >= min && parsed <= max
                      ? parsed
                      : null;
                  _clearSlots();
                }),
              )
            else
              Text('$_minutes minutes'),
            if ((_policy?['required_resource_types'] as List? ?? []).isNotEmpty)
              Text(
                "Required resources: ${(_policy!['required_resource_types'] as List).join(', ')}",
              ),
            for (final resource in resources)
              CheckboxListTile(
                title: Text('${resource['name']}'),
                subtitle: Text('${resource['resource_type']}'),
                value: _resources.contains(resource['id']),
                onChanged: !edit
                    ? null
                    : (selected) => setState(() {
                        final id = resource['id'] as int;
                        if (selected == true && _resources.length < 9) {
                          _resources.add(id);
                        }
                        if (selected == false) _resources.remove(id);
                        _clearSlots();
                      }),
              ),
            for (final id in _resources.where(
              (id) => !resources.any((resource) => resource['id'] == id),
            ))
              CheckboxListTile(
                title: Text('Current resource #$id'),
                value: true,
                onChanged: edit
                    ? (_) => setState(() {
                        _resources.remove(id);
                        _clearSlots();
                      })
                    : null,
              ),
            OutlinedButton(
              onPressed: canCheck ? _loadSlots : null,
              child: const Text('Check available times'),
            ),
            Wrap(
              spacing: 8,
              children: [
                for (final slot in _slots)
                  ChoiceChip(
                    label: Text('${slot['label']}'),
                    selected: _slot == slot,
                    onSelected: edit
                        ? (_) => setState(() => _slot = slot)
                        : null,
                  ),
              ],
            ),
          ],
        ],
      ),
      bottomNavigationBar: SafeArea(
        minimum: const EdgeInsets.fromLTRB(16, 8, 16, 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_busy) const LinearProgressIndicator(),
            if (_notice != null) Text(_notice!, maxLines: 4),
            FilledButton(
              onPressed:
                  _busy || (!grouped && _customer == null) || _slot == null
                  ? null
                  : _confirm,
              child: Text(
                _pending != null
                    ? 'Retry confirmation'
                    : grouped
                    ? 'Save new schedule'
                    : 'Confirm appointment',
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ServicePicker extends StatefulWidget {
  const _ServicePicker({required this.load});

  final Future<Json> Function(String search, int page) load;

  @override
  State<_ServicePicker> createState() => _ServicePickerState();
}

class _ServicePickerState extends State<_ServicePicker> {
  var _search = '';
  var _page = 1;
  late var _results = widget.load(_search, _page);

  void _refresh(String search, int page) => setState(() {
    _search = search;
    _page = page;
    _results = widget.load(search, page);
  });

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Choose service'),
    content: SizedBox(
      width: 360,
      height: 400,
      child: Column(
        children: [
          TextField(
            maxLength: 100,
            decoration: const InputDecoration(labelText: 'Search services'),
            textInputAction: TextInputAction.search,
            onSubmitted: (value) => _refresh(value.trim(), 1),
          ),
          Expanded(
            child: FutureBuilder<Json>(
              future: _results,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return TextButton(
                    onPressed: () => _refresh(_search, _page),
                    child: Text('Retry: ${snapshot.error}'),
                  );
                }
                final data = snapshot.data!;
                final items = (data['items'] as List).whereType<Json>();
                return ListView(
                  children: [
                    if (items.isEmpty)
                      const ListTile(title: Text('No services found')),
                    for (final item in items)
                      ListTile(
                        title: Text('${item['name']}'),
                        onTap: () => Navigator.pop(context, item),
                      ),
                    if (_page > 1)
                      TextButton(
                        onPressed: () => _refresh(_search, _page - 1),
                        child: const Text('Previous services'),
                      ),
                    if ((data['pages'] as int? ?? 1) > _page)
                      TextButton(
                        onPressed: () => _refresh(_search, _page + 1),
                        child: const Text('More services'),
                      ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Cancel'),
      ),
    ],
  );
}
