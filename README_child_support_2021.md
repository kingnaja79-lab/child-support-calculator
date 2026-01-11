# 2021 양육비 산정 자동 계산기 (Python)

서울가정법원 2021년 **양육비 산정기준표** 및 **해설서**의 산정 로직을 그대로 따라,
- 자녀(만 나이)별 표준양육비 자동 조회
- 다자녀 합산
- 자녀 수(1인/2인/3인 이상) 가산·감산 반영
- 소득비례 분담비율(비양육자 부담비율) 계산
- 최종 비양육자 지급액 계산

을 수행합니다.

## 설치
별도 패키지 설치 없이 단일 파일로 동작합니다.

## 빠른 사용 (CLI)
```bash
python child_support_2021.py --cust-income 1800000 --noncust-income 2700000 --children-ages 15,8
```

출력은 JSON이며, 표준양육비 합계(standard_total_krw)와 비양육자 지급액(non_custodial_payment_krw)이 포함됩니다.

## 예시 (기준표 예시와 동일)
- 양육자 180만 / 비양육자 270만 (합산 450만)
- 자녀 2명: 만 15세, 만 8세

결과:
- 표준양육비 합계: 2,542,000원
- 비양육자 부담비율: 60%
- 비양육자 지급액: 1,525,200원

(기준표 예시 설명과 동일한 수치가 산출됩니다.)

## 가산·감산(조정) 적용
기준표/해설서는 가산·감산 요소를 열거하지만, 자녀 수 외에는 단일 고정 배율을 제시하지 않습니다.
따라서 본 모듈은 `Adjustment`로 **사용자가 배율/가산금액을 입력**하도록 설계했습니다.

예: 도시 거주 5% 가산(가상의 정책 입력)
```bash
python child_support_2021.py   --cust-income 1800000 --noncust-income 2700000 --children-ages 15,8   --adj-json '[{"name":"urban","type":"multiplier","value":0.05,"is_percent":true}]'
```

## 라이브러리로 사용
```python
from child_support_2021 import CalculationInputs, Child, calculate_child_support

inp = CalculationInputs(
    custodial_parent_income_krw=1_800_000,
    non_custodial_parent_income_krw=2_700_000,
    children=[Child(age=15), Child(age=8)],
)
out = calculate_child_support(inp)
print(out.non_custodial_payment_krw)
```

## 주의
- 본 코드는 **2021년 표준표** 기반입니다. 이후 개정표 적용이 필요하면 데이터 테이블 교체가 필요합니다.
- 실제 재판·조정에서는 개별 사정(재산, 치료비, 교육비, 회생절차 등)에 따라 조정될 수 있습니다.
