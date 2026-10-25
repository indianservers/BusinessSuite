import 'dart:io';
import 'package:integration_test/integration_test_driver_extended.dart';

Future<void> main() async {
  const directory = 'build/device-qa-v2';
  await Directory(directory).create(recursive: true);
  await integrationDriver(
    writeResponseOnFailure: true,
    responseDataCallback: (data) => writeResponseData(
      data,
      destinationDirectory: directory,
      testOutputFilename: 'pms-features-results',
    ),
    onScreenshot: (name, bytes, [args]) async {
      await File('$directory/$name.png').writeAsBytes(bytes);
      return true;
    },
  );
}
