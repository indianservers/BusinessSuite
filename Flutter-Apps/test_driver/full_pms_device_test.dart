import 'dart:io';
import 'package:integration_test/integration_test_driver_extended.dart';

Future<void> main() async {
  const dir = 'build/full-pms-device';
  await Directory(dir).create(recursive: true);
  await integrationDriver(
    writeResponseOnFailure: true,
    responseDataCallback: (data) => writeResponseData(
      data,
      destinationDirectory: dir,
      testOutputFilename: 'results',
    ),
    onScreenshot: (name, bytes, [args]) async {
      await File('$dir/$name.png').writeAsBytes(bytes);
      return true;
    },
  );
}
