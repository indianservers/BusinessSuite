import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class CompanyProfilePanel extends StatefulWidget {
  const CompanyProfilePanel({super.key, required this.api});
  final ApiClient api;

  @override
  State<CompanyProfilePanel> createState() => _CompanyProfilePanelState();
}

class _CompanyProfilePanelState extends State<CompanyProfilePanel> {
  static const _path = '/access/settings/company-profile';
  static const _fields = {
    'name': 'Company name',
    'legal_name': 'Legal name',
    'website': 'Website',
    'email': 'Company email',
    'phone': 'Phone',
    'address': 'Address',
    'city': 'City',
    'state': 'State',
    'country': 'Country',
    'pincode': 'Postal code',
    'logo_url': 'Logo URL',
    'registration_number': 'Registration number',
    'cin_number': 'CIN',
    'pan_number': 'PAN',
    'tan_number': 'TAN',
    'gstin': 'GSTIN',
  };
  final _form = GlobalKey<FormState>();
  final _changes = <String, dynamic>{};
  late Future<Json> _profile = _load();
  bool _saving = false;
  int _revision = 0;

  Future<Json> _load() async => await widget.api.request('GET', _path) as Json;

  Future<void> _save(int company) async {
    if (_saving || _changes.isEmpty || !_form.currentState!.validate()) return;
    setState(() => _saving = true);
    try {
      await widget.api.request(
        'PATCH',
        _path,
        scopeHeaders: {'X-Suite-Organization': '$company'},
        data: Map<String, dynamic>.of(_changes),
      );
      if (!mounted) return;
      setState(() {
        _changes.clear();
        _revision++;
        _profile = _load();
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Company details saved.')));
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Json>(
    future: _profile,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const Center(child: CircularProgressIndicator());
      }
      final data = snapshot.data;
      final profile = data?['profile'];
      if (data == null || profile is! Json) {
        return Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('${snapshot.error ?? 'Could not load company details.'}'),
              TextButton(
                onPressed: () => setState(() {
                  _profile = _load();
                }),
                child: const Text('Retry'),
              ),
            ],
          ),
        );
      }
      final company = data['companyId'];
      final editable = data['editable'] == true && company is int;
      return Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (!editable) const ListTile(title: Text('Read-only access')),
            for (final field in _fields.entries)
              if (profile.containsKey(field.key))
                Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: TextFormField(
                    key: ValueKey((field.key, _revision)),
                    initialValue: '${profile[field.key] ?? ''}',
                    readOnly: !editable || _saving,
                    decoration: InputDecoration(labelText: field.value),
                    validator: (value) =>
                        field.key == 'name' && (value ?? '').trim().isEmpty
                        ? 'Enter a company name.'
                        : null,
                    onChanged: (value) => setState(() {
                      final clean = value.trim();
                      if (clean == '${profile[field.key] ?? ''}') {
                        _changes.remove(field.key);
                      } else {
                        _changes[field.key] = clean;
                      }
                    }),
                  ),
                ),
            if (editable)
              FilledButton(
                onPressed: _saving || _changes.isEmpty
                    ? null
                    : () => _save(company),
                child: Text(_saving ? 'Saving…' : 'Save company details'),
              ),
          ],
        ),
      );
    },
  );
}
