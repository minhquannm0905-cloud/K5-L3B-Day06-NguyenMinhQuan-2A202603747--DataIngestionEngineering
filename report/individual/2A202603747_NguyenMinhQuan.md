# Báo cáo cá nhân — Day 06 Data Ingestion Engineering

- Họ và tên: Nguyễn Minh Quân
- MSSV: 2A202603747
- Lớp: L3B

## 1. Dữ liệu và pipeline

Corpus gồm chương 3–5 của *Think Stats 2e* (Allen B. Downey), trang in 31–73, theo giấy phép CC BY-NC-SA 4.0. PDF đã cắt có 43 trang vật lý, trong đó 42 trang có nội dung. Trang in 44 chỉ có đầu trang và số trang nhưng vẫn được đưa vào lần chạy này. Trang in 74 đã được bỏ khi cắt PDF. Nguồn, giấy phép và ánh xạ số trang được ghi trong `data/manifest.json`.

Pipeline dùng `pypdf` để trích xuất văn bản, chuẩn hóa Unicode và xử lý từ bị ngắt cuối dòng. Một số khoảng trắng quanh chữ in nghiêng và ký hiệu toán học vẫn bị lỗi khi trích xuất. Khi kiểm tra evidence, script chuẩn hóa dấu và bỏ khoảng trắng trong cả hai chuỗi trước khi so khớp. Kết quả kiểm tra trước khi chạy benchmark là 20/20 đoạn evidence xuất hiện đúng trang.

Embedding dùng `intfloat/e5-small-v2` qua Sentence Transformers, chạy trên CPU và tạo vector 384 chiều. Chunk dùng tiền tố `passage: `, câu hỏi dùng `query: `. Vector được lưu trong PostgreSQL 16.16 với pgvector 0.8.7. Truy xuất top 3 theo cosine distance.

Mỗi chunk lưu `document_id`, `source`, `page_id`, `pdf_page`, `printed_page` và `chapter`. `printed_page` giúp đối chiếu với số in trong sách. `chapter` được gán theo phạm vi trang của từng chương và dùng làm bộ lọc khi câu hỏi chỉ định chương.

## 2. Cấu hình và benchmark

| Cấu hình | Cách chia chunk | Lọc metadata |
|---|---|---|
| A | Cửa sổ 500 ký tự, overlap 50 ký tự, giới hạn trong một trang | Không |
| B | Chia theo đề mục và ưu tiên ranh giới câu, tối đa 500 ký tự. Câu dài hơn giới hạn dùng cửa sổ có overlap 50 ký tự | Không |
| C | Dùng lại chunk và embedding của B | Lọc theo `chapter` khi câu hỏi yêu cầu |

Benchmark gồm 15 câu dev và 5 câu test. `q02`, `q11` và `q16` có điều kiện lọc theo chương. Mỗi câu có đáp án, trang in và đoạn bằng chứng trong `benchmark/questions.json`. Một kết quả được tính là hit tự động khi cùng tài liệu, đúng trang và chứa đủ đoạn bằng chứng sau chuẩn hóa.

Cấu hình B được chọn từ tập dev trước khi chạy test. B và C hòa ở Hit@1 và Evidence Hit@3. B được chọn vì quy trình truy xuất đơn giản hơn trong thí nghiệm này.

## 3. Kết quả

| Cấu hình | Số chunk | Dev Hit@1 | Dev Evidence Hit@3 | Test Hit@1 | Test Evidence Hit@3 |
|---|---:|---:|---:|---:|---:|
| A | 138 | 1/15 | 8/15 | 2/5 | 2/5 |
| B | 157 | 8/15 | 12/15 | 2/5 | 3/5 |
| C | 157, dùng lại B | 8/15 | 12/15 | 2/5 | 3/5 |

Lần nạp chung A và B mất 13,05 giây, gồm tải model vào bộ nhớ, tạo embedding và ghi cơ sở dữ liệu. Không đo thời gian nạp riêng từng cấu hình. Chi phí API là 0 vì embedding chạy local.

| Cấu hình | Coherence trung bình /2 | Metadata đủ và khớp | Tuân thủ bộ lọc | Grounding 0 / 1 / 2 (số câu) | Grounding trung bình /2 |
|---|---:|---:|---|---|---:|
| A | 1,10 (10 mẫu) | 15/15 | Không áp dụng | 1 / 2 / 2 | 1,20 |
| B | 1,50 (10 mẫu) | 15/15 | Không áp dụng | 1 / 1 / 3 | 1,40 |
| C | 1,50 (10 mẫu) | 15/15 | 1/1 câu có lọc | 1 / 1 / 3 | 1,40 |

Coherence được chấm tại vị trí ký tự nội dung cuối trên 10 trang in 31–40. Metadata được kiểm tra trên top 3 của 5 câu test cho mỗi cấu hình bằng cách đối chiếu với bản ghi trang đã trích xuất. Grounding được chấm theo mức độ đầy đủ của bằng chứng trong top 3 và khả năng truy về nguồn.

- Trace tự động: `results/dev_trace.jsonl` và `results/test_trace.jsonl`
- Nhãn chấm thủ công: `results/manual_audit.csv` và `results/coherence_audit.csv`
- Nhật ký thí nghiệm: `artifacts/experiment_log.csv`

## 4. Phân tích và kết luận

**A so với B.** Trên dev, B có thêm 7 câu tìm được bằng chứng ở hạng 1 và thêm 4 câu tìm được trong top 3. Điểm coherence của B cao hơn 0,40 điểm trên mẫu đã chấm. B tạo thêm 19 chunk, nhưng độ dài trung bình giảm từ khoảng 423 xuống 343 ký tự. Với `q18`, cả A và B đều tìm được phương thức `Prob` ở trang 32 ngay hạng 1. Chunk của A bắt đầu giữa từ, còn chunk của B giữ nguyên câu hướng dẫn.

**B so với C.** Với `q16`, bộ lọc C loại một chunk chương 3 khỏi top 3 và trả đủ ba chunk chương 4. Chunk hạng 1 vẫn bị cắt mất cụm “With replacement” ở trang 56. Vì thế, cả ba cấu hình đều thiếu bằng chứng đầy đủ cho câu này. B và C có cùng điểm tổng trên dev và test.

**Lỗi trên test.** Với `q17`, các đoạn tìm được nói về phân vị hoặc CDF nhưng thiếu đủ ba mốc 25, 50 và 75. Với `q20`, A chỉ trả đoạn ở trang 68, nơi có nhắc lognormal nhưng chưa chỉ rõ mô hình phù hợp hơn cho 99% còn lại. B và C truy xuất được kết luận đó ở trang 69, hạng 2.

**Kết luận.** B là cấu hình phù hợp nhất theo tiêu chí đã dùng trên dev. Trên test, B đạt Evidence Hit@3 là 3/5 so với 2/5 của A. Bộ lọc theo chương thu hẹp phạm vi truy xuất ở `q16`. Tập test chỉ có một câu yêu cầu lọc nên kết quả chưa đủ để đánh giá rộng hơn tác động của metadata. Mẫu coherence cũng chỉ gồm vị trí cuối trang trong chương 3. Nếu mở rộng thí nghiệm, cần lấy mẫu ở nhiều chương và vị trí hơn, tăng số câu có điều kiện lọc và kiểm tra cách giữ nội dung nối qua ranh giới trang.