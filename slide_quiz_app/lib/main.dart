import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const SlideQuizApp());
}

class SlideQuizApp extends StatelessWidget {
  const SlideQuizApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SlideQuiz',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF7F8FA),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF6C5CE7),
          primary: const Color(0xFF6C5CE7),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF6C5CE7),
          foregroundColor: Colors.white,
          elevation: 0,
        ),
      ),
      home: const HomeScreen(),
    );
  }
}

class QuestionItem {
  final String question;
  final List<String> options;
  final String answer;

  QuestionItem({
    required this.question,
    required this.options,
    required this.answer,
  });

  factory QuestionItem.fromJson(Map<String, dynamic> json) {
    return QuestionItem(
      question: json['question'] ?? '',
      options: List<String>.from(json['options'] ?? []),
      answer: json['answer'] ?? '',
    );
  }
}

// 1. EKRAN: DOSYA YÜKLEME EKRANI
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  bool isLoading = false;
  int questionCount = 5;

  Future<void> pickAndUploadFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'pptx', 'docx', 'txt'],
        withData: true,
      );

      if (result == null || result.files.isEmpty) return;

      final pickedFile = result.files.first;
      final Uint8List? fileBytes = pickedFile.bytes;

      if (fileBytes == null) {
        showError("Hata: Dosya içeriği okunamadı.");
        return;
      }

      setState(() => isLoading = true);

      // Backend sunucu adresi
      final uri = Uri.parse('https://slidequiz-api.onrender.com/generate-quiz');
      var request = http.MultipartRequest("POST", uri);
      request.fields['question_count'] = questionCount.toString();
      request.files.add(
        http.MultipartFile.fromBytes(
          'file',
          fileBytes,
          filename: pickedFile.name,
        ),
      );

      var streamedResponse = await request.send();
      var response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final Map<String, dynamic> data = jsonDecode(utf8.decode(response.bodyBytes));
        final List<dynamic> qList = data['questions'] ?? [];

        if (qList.isEmpty) {
          showError("Yapay zeka bu belgeden soru üretemedi.");
          return;
        }

        List<QuestionItem> questions =
            qList.map((e) => QuestionItem.fromJson(e)).toList();

        if (mounted) {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (context) => QuizScreen(questions: questions),
            ),
          );
        }
      } else {
        final errorText = utf8.decode(response.bodyBytes);
        showError("Sunucu Hatası (${response.statusCode}): $errorText");
      }
    } catch (e) {
      showError("İstek Hatası: $e");
    } finally {
      if (mounted) {
        setState(() => isLoading = false);
      }
    }
  }

  void showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: Colors.redAccent,
        duration: const Duration(seconds: 5),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SlideQuiz', style: TextStyle(fontWeight: FontWeight.bold)),
        centerTitle: true,
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 90,
                height: 90,
                decoration: BoxDecoration(
                  color: const Color(0xFF6C5CE7).withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.school_rounded,
                  size: 48,
                  color: Color(0xFF6C5CE7),
                ),
              ),
              const SizedBox(height: 24),
              const Text(
                'Slaytlarını Yükle, Sınavını Oluştur',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              const Text(
                'PDF, PPTX veya Word ders notlarından anında test üret.',
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey),
              ),
              const SizedBox(height: 32),
              if (isLoading)
                const Column(
                  children: [
                    CircularProgressIndicator(color: Color(0xFF6C5CE7)),
                    SizedBox(height: 16),
                    Text(
                      'Yapay zeka soruları hazırlıyor, lütfen bekleyin...',
                      style: TextStyle(fontWeight: FontWeight.w500),
                    ),
                  ],
                )
              else
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton.icon(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF6C5CE7),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    onPressed: pickAndUploadFile,
                    icon: const Icon(Icons.upload_file),
                    label: const Text(
                      'Dosya Yükle ve Başla',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

// 2. EKRAN: TESTİ ÇÖZME EKRANI
class QuizScreen extends StatefulWidget {
  final List<QuestionItem> questions;
  const QuizScreen({super.key, required this.questions});

  @override
  State<QuizScreen> createState() => _QuizScreenState();
}

class _QuizScreenState extends State<QuizScreen> {
  int currentIndex = 0;
  Map<int, String> userSelections = {};

  void nextQuestion() {
    if (currentIndex < widget.questions.length - 1) {
      setState(() => currentIndex++);
    } else {
      int score = 0;
      for (int i = 0; i < widget.questions.length; i++) {
        if (userSelections[i] == widget.questions[i].answer) {
          score++;
        }
      }
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (context) => ResultScreen(
            score: score,
            total: widget.questions.length,
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final q = widget.questions[currentIndex];

    return Scaffold(
      appBar: AppBar(
        title: Text('Soru ${currentIndex + 1} / ${widget.questions.length}'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            LinearProgressIndicator(
              value: (currentIndex + 1) / widget.questions.length,
              backgroundColor: Colors.grey.shade300,
              color: const Color(0xFF6C5CE7),
            ),
            const SizedBox(height: 24),
            Text(
              q.question,
              style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 20),
            Expanded(
              child: ListView.builder(
                itemCount: q.options.length,
                itemBuilder: (context, index) {
                  final option = q.options[index];
                  final isSelected = userSelections[currentIndex] == option;

                  return Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? const Color(0xFF6C5CE7).withOpacity(0.1)
                          : Colors.white,
                      border: Border.all(
                        color: isSelected
                            ? const Color(0xFF6C5CE7)
                            : Colors.grey.shade300,
                        width: isSelected ? 2 : 1,
                      ),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: ListTile(
                      title: Text(option),
                      leading: Icon(
                        isSelected
                            ? Icons.check_circle
                            : Icons.radio_button_unchecked,
                        color: isSelected ? const Color(0xFF6C5CE7) : Colors.grey,
                      ),
                      onTap: () {
                        setState(() {
                          userSelections[currentIndex] = option;
                        });
                      },
                    ),
                  );
                },
              ),
            ),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF6C5CE7),
                foregroundColor: Colors.white,
                minimumSize: const Size(double.infinity, 50),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              onPressed: userSelections[currentIndex] == null ? null : nextQuestion,
              child: Text(
                currentIndex == widget.questions.length - 1
                    ? 'Sınavı Bitir'
                    : 'Sonraki Soru',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// 3. EKRAN: SONUÇ EKRANI
class ResultScreen extends StatelessWidget {
  final int score;
  final int total;

  const ResultScreen({super.key, required this.score, required this.total});

  @override
  Widget build(BuildContext context) {
    final percentage = ((score / total) * 100).toInt();

    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(
                Icons.emoji_events_rounded,
                size: 84,
                color: Color(0xFF6C5CE7),
              ),
              const SizedBox(height: 16),
              const Text(
                'Tebrikler!',
                style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 8),
              Text(
                'Sınavı Tamamladın',
                style: TextStyle(fontSize: 16, color: Colors.grey.shade600),
              ),
              const SizedBox(height: 24),
              Text(
                '%$percentage',
                style: const TextStyle(
                  fontSize: 48,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFF6C5CE7),
                ),
              ),
              Text('$score / $total Doğru', style: const TextStyle(fontSize: 18)),
              const SizedBox(height: 36),
              ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF6C5CE7),
                  foregroundColor: Colors.white,
                  minimumSize: const Size(200, 48),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                onPressed: () => Navigator.pop(context),
                child: const Text('Yeni Sınav Oluştur'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}