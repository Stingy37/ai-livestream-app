Project members: Andy Shi    Jatin Sarabu    Jonathan Tran    Nirvaan Thawani    Trinh Gia Anh    Ayushi Dalal    Anmol Mrig    Esther Wang    Karthik Sista    Aiden Wang    Evelyn Ding    Yitong Zhong    James Lee    Fiona Zhao    Jingyi Wu

## Running the Typhoon Champi desk

See [docs/PIPELINE.md](docs/PIPELINE.md). Short version: drop the Lumen API keys into
`secrets/lumen_keys.txt` (one per line), then `bash scripts/run_livestream.sh`. The website is served
by the EC2 instance (`ec2/README.md`); until port 8443 is opened in its security group, view it through
`ssh -i ~/.ssh/weather-dev -L 8443:127.0.0.1:8443 ubuntu@54.221.147.143` at https://localhost:8443/.
