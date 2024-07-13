import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";

const GlossyContainer = ({
  children,
  className = "sm:w-[45vw] lg:w-[30vw] h-[15vh]",
  degree = 4,
  radius = "250",
  brightness = "0.2",
  gradientPoint = "ellipse_at_top_left",
  gradientColor = "from-slate-800 via-gray-900 to-slate-900",
  shadow = true,
}) => {
  const containerRef = useRef(null);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [isHovering, setIsHovering] = useState(false);
  const [opacity, setOpacity] = useState(0);

  useEffect(() => {
    const handleMouseMove = (event) => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        setMousePosition({ x, y });

        // Calculate rotation based on mouse position
        const rotateX = ((y - rect.height / 2) / rect.height) * degree; //
        const rotateY = ((x - rect.width / 2) / rect.width) * degree; //

        containerRef.current.style.transform = `perspective(1000px) rotateX(${-rotateX}deg) rotateY(${rotateY}deg)`;
      }
    };

    const handleMouseEnter = () => {
      setIsHovering(true);
      setOpacity(1);
    };

    const handleMouseLeave = () => {
      setIsHovering(false);
      setOpacity(0);
      if (containerRef.current) {
        containerRef.current.style.transform =
          "perspective(1000px) rotateX(0deg) rotateY(0deg)";
      }
    };

    const container = containerRef.current;
    if (container) {
      container.addEventListener("mousemove", handleMouseMove);
      container.addEventListener("mouseenter", handleMouseEnter);
      container.addEventListener("mouseleave", handleMouseLeave);
    }

    return () => {
      if (container) {
        container.removeEventListener("mousemove", handleMouseMove);
        container.removeEventListener("mouseenter", handleMouseEnter);
        container.removeEventListener("mouseleave", handleMouseLeave);
      }
    };
  }, []);

  const gradientStyle = {
    background: `radial-gradient(circle ${radius}px at ${mousePosition.x}px ${mousePosition.y}px, rgba(125,20,205,${brightness}), transparent 80%)`,
  };

  return (
    <motion.div
      ref={containerRef}
      className={`${className}`}
      style={{
        transformStyle: "preserve-3d",
        transition: "transform 0.2s ease-out",
        willChange: "transform",
        // overflow: "hidden",
      }}
    >
      <div
        className={`absolute inset-0 rounded-lg overflow-hidden bg-[radial-gradient(${gradientPoint},_var(--tw-gradient-stops))] ${gradientColor} `}
        style={{
          boxShadow: shadow ? "5px 5px 10px rgba(0, 0, 0, 0.1)" : "",
          backdropFilter: "blur(5px)",
          WebkitBackdropFilter: "blur(5px)",
        }}
      >
        <div
          className="absolute inset-0 z-30 rounded-lg pointer-events-none transition-opacity duration-500"
          style={{
            boxShadow: "inset 0 0 0 1.5px rgba(128, 128, 128, 0.2)",
            opacity: isHovering ? 1 : 0.5,
          }}
        />
        <div
          className="absolute inset-0 pointer-events-none transition-opacity duration-500"
          style={{
            ...gradientStyle,
            opacity: opacity,
            filter: "blur(40px)",
          }}
        />
      </div>
      <div className="absolute inset-0 overflow-hidden rounded-lg">
        <div className="relative z-10 ">
          {React.Children.map(children, (child) =>
            React.cloneElement(child, {
              style: {
                ...child.props.style,
                // transform: `translateZ(10px)`,
                // transition: "transform 0.3s ease-out", //3d popout duration
              },
            })
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default GlossyContainer;
