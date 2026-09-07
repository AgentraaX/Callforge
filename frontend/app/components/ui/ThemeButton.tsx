import Link from "next/link";
import type {
  AnchorHTMLAttributes,
  ButtonHTMLAttributes,
  ReactNode,
} from "react";

/* One button. Replaces the two parallel systems:
   - CSS .btn-teal / .btn-white (globals.css) used by the landing page
   - PrimaryButton / GhostButton (app/dashboard/_components/ui.tsx)

   Renders <Link> for internal hrefs ("/..."), <a> for anchors / external /
   mailto, and <button> otherwise. */

type Variant = "primary" | "secondary" | "ghost";
type Size = "sm" | "md" | "lg";

interface CommonProps {
  variant?: Variant;
  size?: Size;
  iconRight?: ReactNode;
  iconLeft?: ReactNode;
  fullWidth?: boolean;
  className?: string;
  children: ReactNode;
}

type LinkLikeProps = CommonProps &
  Omit<AnchorHTMLAttributes<HTMLAnchorElement>, keyof CommonProps> & {
    href: string;
  };

type ButtonLikeProps = CommonProps &
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, keyof CommonProps> & {
    href?: undefined;
  };

type Props = LinkLikeProps | ButtonLikeProps;

const BASE =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-control font-semibold " +
  "transition-[transform,background-color,box-shadow,color] duration-150 ease-out " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 " +
  "active:scale-[0.97] disabled:pointer-events-none disabled:opacity-40";

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-[12.5px]",
  md: "h-10 px-4 text-[13.5px]",
  lg: "h-11 px-6 text-[14px]",
};

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-signal text-white hover:bg-signal-hover hover:-translate-y-px hover:shadow-[0_6px_20px_-4px_rgba(59,111,229,0.6)]",
  secondary:
    "bg-white/[0.06] text-ink shadow-[inset_0_0_0_1px_var(--color-hairline-strong)] " +
    "hover:bg-white/[0.12] hover:-translate-y-px",
  ghost: "text-slate hover:bg-white/[0.06] hover:text-ink",
};

export default function ThemeButton(props: Props) {
  const {
    variant = "primary",
    size = "md",
    iconRight,
    iconLeft,
    fullWidth,
    className = "",
    children,
    href,
    ...rest
  } = props;

  const cls = [
    BASE,
    SIZES[size],
    VARIANTS[variant],
    fullWidth ? "w-full" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const content = (
    <>
      {iconLeft}
      {children}
      {iconRight}
    </>
  );

  if (typeof href === "string") {
    const anchorRest = rest as AnchorHTMLAttributes<HTMLAnchorElement>;
    const external = /^(https?:|mailto:|tel:)/.test(href) || href.startsWith("#");
    if (external) {
      return (
        <a href={href} className={cls} {...anchorRest}>
          {content}
        </a>
      );
    }
    return (
      <Link href={href} className={cls} {...anchorRest}>
        {content}
      </Link>
    );
  }

  return (
    <button className={cls} {...(rest as ButtonHTMLAttributes<HTMLButtonElement>)}>
      {content}
    </button>
  );
}
