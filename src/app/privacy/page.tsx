import Link from "next/link";
import { InfoPage, infoMetadata } from "@/components/info-page";

export const metadata = infoMetadata(
  "개인정보 처리방침",
  "Mallow Info Lab의 개인정보 처리방침입니다. 수집 항목, 쿠키, Google AdSense, 제휴 링크를 적습니다.",
  "/privacy/",
);

export default function PrivacyPage() {
  return (
    <InfoPage kicker="개인정보" title="개인정보 처리방침" lede="시행일 2026년 11월 12일">
      <p>
        마이멜로(MyMallow, 이하 “운영자”)는 Mallow Info Lab(
        <a href="https://blog.mymallow.cloud/">https://blog.mymallow.cloud/</a>
        )을 운영하면서 이용자의 개인정보를 어떻게 다루는지 이 방침에 적습니다.
      </p>
      <h2>수집하는 정보</h2>
      <p>
        이 사이트에는 회원가입, 댓글, 뉴스레터, 문의 양식이 없습니다. 이용자가 이름, 이메일, 전화번호를
        입력하는 절차도 없습니다. 운영자는 그런 경로로 개인정보를 수집하지 않습니다.
      </p>
      <p>
        페이지를 열 때 브라우저와 호스팅 환경 사이에서 접속에 필요한 기술 정보(IP 주소, 브라우저 종류,
        요청 시각 등)가 전달될 수 있습니다. 이 사이트는 GitHub Pages로 게시됩니다. 그 과정에서 생기는
        접속 기록은 호스팅 제공자의 정책에 따릅니다.
      </p>
      <h2>쿠키와 Google AdSense</h2>
      <p>
        이 사이트는 Google AdSense 게시자 계정 <strong>ca-pub-5854572232694460</strong>과 연결되어
        있습니다. 각 페이지의 <strong>google-adsense-account</strong> 메타 태그와 사이트 루트의{" "}
        <a href="https://blog.mymallow.cloud/ads.txt">ads.txt</a>가 그 계정을 알립니다.
      </p>
      <p>
        현재 목록과 글 화면에는 광고를 그리는 스크립트를 넣지 않습니다. 그래서 이 페이지들이 직접 광고
        쿠키를 저장하지는 않습니다. 광고가 게재되면 Google이 광고 제공, 측정, 맞춤 설정을 위해 쿠키를
        사용할 수 있습니다. Google이 광고에 쿠키를 쓰는 방식은 아래에서 확인할 수 있습니다.
      </p>
      <ul>
        <li>
          <a href="https://policies.google.com/technologies/ads" target="_blank" rel="noopener noreferrer">
            Google 광고 쿠키 안내
          </a>
        </li>
        <li>
          <a href="https://adssettings.google.com/" target="_blank" rel="noopener noreferrer">
            Google 광고 설정
          </a>
        </li>
      </ul>
      <h2>방문 분석</h2>
      <p>
        Google Analytics를 비롯한 방문 분석 도구는 현재 사용하지 않습니다. 분석용 쿠키를 심지 않습니다.
        분석 도구를 도입하면 이 방침을 먼저 고칩니다.
      </p>
      <h2>제휴 링크</h2>
      <p>
        쿠팡 파트너스를 포함한 제휴 마케팅 링크는 현재 사용하지 않습니다. 제휴 링크를 넣게 되면, 그
        링크를 통한 구매로 운영자가 수수료를 받을 수 있다는 점을 해당 글과 이 방침에 함께 적습니다.
        수수료는 구매자의 결제 금액에 더해지지 않습니다.
      </p>
      <h2>보관과 제3자 제공</h2>
      <p>
        운영자가 이용자에게서 직접 수집하는 개인정보가 없으므로, 운영자가 보관하거나 판매하는 개인정보도
        없습니다. 광고가 게재되는 시점부터는 위 Google AdSense 항목의 제3자 처리가 적용됩니다.
      </p>
      <h2>이용자의 선택</h2>
      <p>
        브라우저 설정에서 쿠키 저장을 거부하거나 이미 저장된 쿠키를 지울 수 있습니다. 쿠키를 끄면 광고나
        일부 외부 기능이 제한될 수 있습니다.
      </p>
      <h2>방침의 변경</h2>
      <p>이 방침이 바뀌면 이 페이지에 새 시행일을 적어 게시합니다.</p>
      <h2>운영자</h2>
      <p>
        운영 주체는{" "}
        <a href="https://mymallow.cloud/" target="_blank" rel="noopener noreferrer">
          마이멜로 (MyMallow)
        </a>
        입니다. 사이트 이용 조건은 <Link href="/terms/">이용약관</Link>에 적혀 있습니다.
      </p>
    </InfoPage>
  );
}
