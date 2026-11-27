import 'dart:typed_data';

import 'package:dio/dio.dart';

import 'api_client.dart';

Future<Uint8List> fetchSuitePdf(
  ApiClient api,
  String path, {
  Map<String, dynamic> query = const {},
  Map<String, String> scopeHeaders = const {},
}) async {
  final result =
      await api.request(
            'GET',
            path,
            query: query,
            scopeHeaders: scopeHeaders,
            responseType: ResponseType.bytes,
            returnResponse: true,
          )
          as Response;
  final data = result.data;
  if (result.statusCode != 200 ||
      data is! List<int> ||
      data.length < 5 ||
      String.fromCharCodes(data.take(5)) != '%PDF-') {
    throw ApiFailure('The server did not return a PDF.');
  }
  return Uint8List.fromList(data);
}
