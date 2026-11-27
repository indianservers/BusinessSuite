import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/models.dart';

class CrmCpqEvaluator extends StatefulWidget {
  const CrmCpqEvaluator({
    super.key,
    required this.api,
    required this.scopeHeaders,
  });

  final ApiClient api;
  final Map<String, String> scopeHeaders;

  @override
  State<CrmCpqEvaluator> createState() => _CrmCpqEvaluatorState();
}

class _CrmCpqEvaluatorState extends State<CrmCpqEvaluator> {
  final _form = GlobalKey<FormState>();
  final _amount = TextEditingController(text: '250000');
  final _discount = TextEditingController(text: '0');
  Json? _result;
  String? _error;
  bool _evaluating = false;

  @override
  void dispose() {
    _amount.dispose();
    _discount.dispose();
    super.dispose();
  }

  Future<void> _evaluate() async {
    if (_evaluating || !_form.currentState!.validate()) return;
    final revision = widget.api.sessionRevision;
    setState(() {
      _evaluating = true;
      _result = null;
      _error = null;
    });
    try {
      final result = await widget.api.request(
        'POST',
        '/crm/cpq/evaluate',
        scopeHeaders: widget.scopeHeaders,
        data: {
          'amount': num.parse(_amount.text.trim()),
          'discount': num.parse(_discount.text.trim()),
        },
      );
      if (!mounted || revision != widget.api.sessionRevision) return;
      if (result is! Json || result['ruleCount'] is! int) {
        throw ApiFailure('The server returned an invalid evaluation.');
      }
      setState(() => _result = result);
    } on ApiFailure catch (error) {
      if (mounted && revision == widget.api.sessionRevision) {
        setState(() => _error = error.message);
      }
    } finally {
      if (mounted) setState(() => _evaluating = false);
    }
  }

  Widget _field(String label, TextEditingController controller) =>
      TextFormField(
        controller: controller,
        enabled: !_evaluating,
        decoration: InputDecoration(labelText: label),
        keyboardType: const TextInputType.numberWithOptions(decimal: true),
        onChanged: (_) {
          if (_result != null || _error != null) {
            setState(() {
              _result = null;
              _error = null;
            });
          }
        },
        validator: (text) {
          final value = num.tryParse(text?.trim() ?? '');
          return value == null || !value.isFinite || value < 0
              ? 'Enter a number of zero or more.'
              : null;
        },
      );

  @override
  Widget build(BuildContext context) {
    final result = _result;
    final warnings = (result?['warnings'] as List? ?? const [])
        .whereType<Json>();
    final recommendations = (result?['recommendations'] as List? ?? const [])
        .whereType<Json>();
    return Scaffold(
      appBar: AppBar(title: const Text('Evaluate CPQ rules')),
      body: Form(
        key: _form,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _field('Amount', _amount),
            _field('Discount', _discount),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _evaluating ? null : _evaluate,
              child: Text(_evaluating ? 'Evaluating…' : 'Evaluate'),
            ),
            if (_error case final String error)
              Text(
                error,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            if (result != null) ...[
              ListTile(title: Text("Rules checked: ${result['ruleCount']}")),
              ListTile(title: Text('Warnings: ${warnings.length}')),
              for (final rule in warnings)
                ListTile(title: Text("${rule['rule'] ?? 'Warning'}")),
              ListTile(
                title: Text('Recommendations: ${recommendations.length}'),
              ),
              for (final rule in recommendations)
                ListTile(title: Text("${rule['rule'] ?? 'Recommendation'}")),
            ],
          ],
        ),
      ),
    );
  }
}
